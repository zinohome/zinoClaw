#!/usr/bin/env python3
"""
B站 API 调用脚本
用法: python3 bili_call.py <tool_name> [json_args]
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List

SCRIPT_DIR = Path(__file__).parent
SKILL_DIR = SCRIPT_DIR.parent
DATA_DIR = SKILL_DIR / "data"
QR_CODE_FILE = DATA_DIR / "qrcode.png"
COVER_FILE = DATA_DIR / "auto_cover.jpg"

DATA_DIR.mkdir(parents=True, exist_ok=True)

import credential_store


def extract_video_cover(video_path: str, output_path: str = None, time_sec: float = 1.0) -> Optional[str]:
    """
    从视频中提取封面图片
    优先使用 ffmpeg，如果没有则使用 OpenCV
    
    Args:
        video_path: 视频文件路径
        output_path: 输出图片路径，默认使用 DATA_DIR/auto_cover.jpg
        time_sec: 截取的时间点（秒）
    
    Returns:
        成功返回图片路径，失败返回 None
    """
    import subprocess
    import shutil
    
    if output_path is None:
        output_path = str(COVER_FILE)
    
    # 方法1: 尝试使用 ffmpeg
    if shutil.which('ffmpeg'):
        try:
            cmd = [
                'ffmpeg', '-y',
                '-ss', str(time_sec),
                '-i', video_path,
                '-vframes', '1',
                '-q:v', '2',
                output_path
            ]
            result = subprocess.run(cmd, capture_output=True, timeout=30)
            if result.returncode == 0 and Path(output_path).exists():
                return output_path
        except Exception:
            pass
    
    # 方法2: 使用 OpenCV
    try:
        import cv2
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return None
        
        # 跳到指定时间
        cap.set(cv2.CAP_PROP_POS_MSEC, time_sec * 1000)
        ret, frame = cap.read()
        cap.release()
        
        if ret:
            cv2.imwrite(output_path, frame)
            return output_path
    except ImportError:
        pass
    except Exception:
        pass
    
    return None


def load_credential():
    """从加密存储加载凭据"""
    try:
        from bilibili_api import Credential

        data = credential_store.load()
        if not data:
            return None

        sessdata = data.get('sessdata')
        bili_jct = data.get('bili_jct')
        if not (sessdata and bili_jct):
            return None

        return Credential(
            sessdata=sessdata,
            bili_jct=bili_jct,
            buvid3=data.get('buvid3'),
            dedeuserid=data.get('dedeuserid'),
            ac_time_value=data.get('ac_time_value')
        )
    except Exception as e:
        print(f"加载凭据失败: {e}", file=sys.stderr)
    return None


def save_credential(credential):
    """加密保存凭据"""
    data = {
        'sessdata': credential.sessdata,
        'bili_jct': credential.bili_jct,
        'buvid3': credential.buvid3,
        'dedeuserid': credential.dedeuserid,
        'ac_time_value': credential.ac_time_value,
    }
    return credential_store.save(data)


def clear_credential():
    """删除凭据"""
    return credential_store.clear()


async def check_login():
    """检查登录状态"""
    credential = load_credential()
    if not credential:
        return {"logged_in": False, "message": "未找到凭据，请先扫码登录"}
    
    try:
        from bilibili_api import user
        # 尝试获取自己的信息来验证凭据
        self_info = await user.get_self_info(credential)
        return {
            "logged_in": True,
            "uid": self_info.get('mid'),
            "name": self_info.get('name'),
            "level": self_info.get('level')
        }
    except Exception as e:
        return {"logged_in": False, "message": f"凭据已过期或无效: {str(e)}"}


async def get_login_qrcode():
    """获取登录二维码，自动打开并轮询等待扫码完成（最长 120 秒）"""
    try:
        from bilibili_api.login_v2 import QrCodeLogin, QrCodeLoginEvents
        import subprocess, platform

        login_instance = QrCodeLogin()
        await login_instance.generate_qrcode()

        qr_pic = login_instance.get_qrcode_picture()
        qr_pic.to_file(str(QR_CODE_FILE))

        qr_key = login_instance._QrCodeLogin__qr_key
        qr_key_file = DATA_DIR / "qrcode_key.json"
        with open(qr_key_file, 'w') as f:
            json.dump({"qr_key": qr_key}, f)

        try:
            if platform.system() == "Darwin":
                subprocess.Popen(["open", str(QR_CODE_FILE)])
            elif platform.system() == "Linux":
                subprocess.Popen(["xdg-open", str(QR_CODE_FILE)])
            elif platform.system() == "Windows":
                os.startfile(str(QR_CODE_FILE))
        except Exception:
            pass

        for _ in range(40):
            await asyncio.sleep(3)
            try:
                events = await login_instance.check_state()
                if events == QrCodeLoginEvents.TIMEOUT:
                    qr_key_file.unlink(missing_ok=True)
                    return {"success": False, "error": "二维码已过期，请重新调用 get_login_qrcode"}
                if login_instance.has_done():
                    credential = login_instance.get_credential()
                    save_credential(credential)
                    qr_key_file.unlink(missing_ok=True)
                    return {"success": True, "message": "登录成功！凭据已加密保存"}
            except Exception:
                pass

        qr_key_file.unlink(missing_ok=True)
        return {"success": False, "error": "等待超时（120秒），请重新调用 get_login_qrcode"}
    except Exception as e:
        return {"success": False, "error": f"获取二维码失败: {str(e)}"}


async def check_qrcode_status():
    """检查二维码扫描状态（支持跨进程调用）"""
    try:
        from bilibili_api.login_v2 import QrCodeLogin, QrCodeLoginEvents
        
        # 从文件读取 qr_key
        qr_key_file = DATA_DIR / "qrcode_key.json"
        if not qr_key_file.exists():
            return {"status": "error", "message": "没有活跃的登录会话，请先调用 get_login_qrcode"}
        
        with open(qr_key_file, 'r') as f:
            qr_data = json.load(f)
        
        qr_key = qr_data.get('qr_key')
        if not qr_key:
            return {"status": "error", "message": "二维码信息无效，请重新调用 get_login_qrcode"}
        
        # 创建登录实例并恢复 qr_key
        login_instance = QrCodeLogin()
        login_instance._QrCodeLogin__qr_key = qr_key
        
        # 检查状态
        events = await login_instance.check_state()
        
        if events == QrCodeLoginEvents.SCAN:
            return {"status": "scanned", "message": "已扫描，请在手机上确认"}
        elif events == QrCodeLoginEvents.CONF:
            return {"status": "confirmed", "message": "已确认，正在获取凭据..."}
        elif events == QrCodeLoginEvents.TIMEOUT:
            # 清理过期的 qr_key
            qr_key_file.unlink(missing_ok=True)
            return {"status": "timeout", "message": "二维码已过期，请重新调用 get_login_qrcode"}
        elif login_instance.has_done():
            # 获取凭据并保存
            credential = login_instance.get_credential()
            save_credential(credential)
            # 清理 qr_key 文件
            qr_key_file.unlink(missing_ok=True)
            return {"status": "done", "message": "登录成功！"}
        else:
            return {"status": "waiting", "message": "等待扫描..."}
    except Exception as e:
        return {"status": "error", "message": str(e)}


async def logout():
    """退出登录（清除环境变量中的凭据）"""
    try:
        if clear_credential():
            return {"success": True, "message": "已退出登录，凭据已从环境变量中清除"}
        else:
            return {"success": False, "error": "清除凭据失败"}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def publish_dynamic(text: str, images: List[str] = None, topic_id: int = None, 
                          at_uids: List[int] = None, schedule_time: str = None):
    """发布动态"""
    credential = load_credential()
    if not credential:
        return {"success": False, "error": "未登录，请先扫码登录"}
    
    try:
        from bilibili_api import dynamic
        from bilibili_api.utils.picture import Picture
        
        # 构建动态
        builder = dynamic.BuildDynamic.empty()
        builder.add_plain_text(text)
        
        # 添加图片
        if images:
            for img_path in images:
                pic = Picture.from_file(img_path)
                builder.add_image(pic)
        
        # 设置话题
        if topic_id:
            builder.set_topic(topic_id)
        
        # 设置定时发布
        if schedule_time:
            from datetime import datetime
            dt = datetime.fromisoformat(schedule_time)
            builder.set_send_time(dt)
        
        # 发布
        result = await dynamic.send_dynamic(builder, credential)

        dynamic_id = (
            result.get('dynamic_id_str')
            or result.get('dynamic_id')
            or result.get('dyn_id_str')
            or result.get('dyn_id')
            or str(result.get('dynid', ''))
            or None
        )
        if not dynamic_id and isinstance(result, dict):
            for k, v in result.items():
                if 'id' in k.lower() and v:
                    dynamic_id = str(v)
                    break

        return {
            "success": True,
            "dynamic_id": dynamic_id,
            "raw_keys": list(result.keys()) if isinstance(result, dict) else None,
            "message": "动态发布成功"
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


async def upload_video(video_path: str, title: str, tid: int, cover: str = None,
                       desc: str = "", tags: List[str] = None, dynamic: str = "",
                       original: bool = True, source: str = None):
    """上传视频（如果没有提供封面，会自动从视频中提取）"""
    credential = load_credential()
    if not credential:
        return {"success": False, "error": "未登录，请先扫码登录"}
    
    # 检查视频文件是否存在
    if not Path(video_path).exists():
        return {"success": False, "error": f"视频文件不存在: {video_path}"}
    
    try:
        from bilibili_api import video_uploader
        from bilibili_api.utils.picture import Picture
        
        # 准备视频页
        page = video_uploader.VideoUploaderPage(
            path=video_path,
            title=title,
            description=desc
        )
        
        # 准备标签
        if not tags:
            tags = ["视频"]
        
        # 准备封面（如果没有提供，自动从视频提取）
        cover_path = cover
        auto_extracted = False
        
        if not cover_path:
            extracted = extract_video_cover(video_path)
            if extracted:
                cover_path = extracted
                auto_extracted = True
            else:
                return {"success": False, "error": "未提供封面且无法自动提取，请安装 ffmpeg 或 opencv-python"}
        
        if not Path(cover_path).exists():
            return {"success": False, "error": f"封面文件不存在: {cover_path}"}
        
        cover_pic = Picture.from_file(cover_path)
        
        # 准备元数据参数
        meta_kwargs = {
            'tid': tid,
            'title': title,
            'desc': desc,
            'tags': tags,
            'original': original,
            'dynamic': dynamic,
            'cover': cover_pic
        }
        if not original and source:
            meta_kwargs['source'] = source
        
        meta = video_uploader.VideoMeta(**meta_kwargs)
        
        # 创建上传器参数
        uploader_kwargs = {
            'pages': [page],
            'meta': meta,
            'credential': credential
        }
        if cover_pic:
            uploader_kwargs['cover'] = cover_pic
        
        uploader = video_uploader.VideoUploader(**uploader_kwargs)
        
        # 上传
        result = await uploader.start()
        
        response = {
            "success": True,
            "bvid": result.get('bvid'),
            "aid": result.get('aid'),
            "message": "视频上传成功，等待审核"
        }
        
        if auto_extracted:
            response["note"] = "封面已自动从视频中提取"
        
        return response
    except Exception as e:
        return {"success": False, "error": str(e)}


async def search_video(keyword: str, page: int = 1):
    """搜索视频"""
    try:
        from bilibili_api import search
        
        result = await search.search_by_type(keyword, search_type=search.SearchObjectType.VIDEO, page=page)
        
        videos = []
        for item in result.get('result', []):
            videos.append({
                'bvid': item.get('bvid'),
                'title': item.get('title', '').replace('<em class="keyword">', '').replace('</em>', ''),
                'author': item.get('author'),
                'play': item.get('play'),
                'description': item.get('description', '')[:100]
            })
        
        return {
            "success": True,
            "total": result.get('numResults', 0),
            "page": page,
            "videos": videos
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


async def search_user(keyword: str, page: int = 1):
    """搜索用户"""
    try:
        from bilibili_api import search
        
        result = await search.search_by_type(keyword, search_type=search.SearchObjectType.USER, page=page)
        
        users = []
        for item in result.get('result', []):
            users.append({
                'mid': item.get('mid'),
                'uname': item.get('uname'),
                'fans': item.get('fans'),
                'videos': item.get('videos'),
                'sign': item.get('usign', '')[:50]
            })
        
        return {
            "success": True,
            "total": result.get('numResults', 0),
            "page": page,
            "users": users
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


async def get_video_info(bvid: str):
    """获取视频信息"""
    try:
        from bilibili_api import video
        
        v = video.Video(bvid=bvid)
        info = await v.get_info()
        
        return {
            "success": True,
            "bvid": info.get('bvid'),
            "aid": info.get('aid'),
            "title": info.get('title'),
            "desc": info.get('desc'),
            "owner": {
                "mid": info.get('owner', {}).get('mid'),
                "name": info.get('owner', {}).get('name')
            },
            "stat": {
                "view": info.get('stat', {}).get('view'),
                "danmaku": info.get('stat', {}).get('danmaku'),
                "reply": info.get('stat', {}).get('reply'),
                "favorite": info.get('stat', {}).get('favorite'),
                "coin": info.get('stat', {}).get('coin'),
                "share": info.get('stat', {}).get('share'),
                "like": info.get('stat', {}).get('like')
            }
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


async def get_user_info(mid: int):
    """获取用户信息"""
    try:
        from bilibili_api import user
        
        u = user.User(uid=mid)
        info = await u.get_user_info()
        
        return {
            "success": True,
            "mid": info.get('mid'),
            "name": info.get('name'),
            "sign": info.get('sign'),
            "level": info.get('level'),
            "fans": info.get('follower', 0),
            "following": info.get('following', 0)
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


async def like_video(bvid: str, unlike: bool = False):
    """点赞/取消点赞视频"""
    credential = load_credential()
    if not credential:
        return {"success": False, "error": "未登录，请先扫码登录"}
    
    try:
        from bilibili_api import video
        
        v = video.Video(bvid=bvid, credential=credential)
        await v.like(status=not unlike)
        
        return {
            "success": True,
            "message": "取消点赞成功" if unlike else "点赞成功"
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


async def coin_video(bvid: str, num: int = 1, like: bool = False):
    """投币"""
    credential = load_credential()
    if not credential:
        return {"success": False, "error": "未登录，请先扫码登录"}
    
    try:
        from bilibili_api import video
        
        v = video.Video(bvid=bvid, credential=credential)
        await v.pay_coin(num=num, like=like)
        
        return {
            "success": True,
            "message": f"投币 {num} 个成功" + ("，同时点赞" if like else "")
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


async def favorite_video(bvid: str, add_media_ids: List[int] = None):
    """收藏视频。若未指定收藏夹，自动收藏到默认收藏夹。"""
    credential = load_credential()
    if not credential:
        return {"success": False, "error": "未登录，请先扫码登录"}
    
    try:
        from bilibili_api import video, favorite_list, user

        if not add_media_ids:
            self_info = await user.get_self_info(credential)
            mid = self_info['mid']
            fav_result = await favorite_list.get_video_favorite_list(uid=mid, credential=credential)
            fav_list = fav_result.get('list', [])
            if not fav_list:
                return {"success": False, "error": "未找到任何收藏夹，请先创建一个"}
            add_media_ids = [fav_list[0]['id']]

        v = video.Video(bvid=bvid, credential=credential)
        await v.set_favorite(add_media_ids=add_media_ids)
        
        return {
            "success": True,
            "message": f"收藏成功（收藏夹ID: {add_media_ids}）"
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


async def comment_video(bvid: str, text: str):
    """评论视频"""
    credential = load_credential()
    if not credential:
        return {"success": False, "error": "未登录，请先扫码登录"}
    
    try:
        from bilibili_api import video, comment
        
        v = video.Video(bvid=bvid, credential=credential)
        info = await v.get_info()
        aid = info['aid']
        
        result = await comment.send_comment(
            text=text,
            oid=aid,
            type_=comment.CommentResourceType.VIDEO,
            credential=credential
        )
        
        return {
            "success": True,
            "rpid": result.get('rpid'),
            "message": "评论成功"
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


async def like_dynamic(dynamic_id: int, unlike: bool = False):
    """点赞/取消点赞动态"""
    credential = load_credential()
    if not credential:
        return {"success": False, "error": "未登录，请先扫码登录"}
    
    try:
        from bilibili_api import dynamic
        
        d = dynamic.Dynamic(dynamic_id=dynamic_id, credential=credential)
        await d.set_like(status=not unlike)
        
        return {
            "success": True,
            "message": "取消点赞成功" if unlike else "点赞成功"
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


async def repost_dynamic(dynamic_id: int, text: str = "转发动态"):
    """转发动态"""
    credential = load_credential()
    if not credential:
        return {"success": False, "error": "未登录，请先扫码登录"}
    
    try:
        from bilibili_api import dynamic
        
        d = dynamic.Dynamic(dynamic_id=dynamic_id, credential=credential)
        result = await d.repost(text=text)
        
        return {
            "success": True,
            "dynamic_id": result.get('dynamic_id_str'),
            "message": "转发成功"
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


async def get_my_dynamics(page: int = 1):
    """获取我的动态列表"""
    credential = load_credential()
    if not credential:
        return {"success": False, "error": "未登录，请先扫码登录"}
    
    try:
        from bilibili_api import dynamic, user
        
        self_info = await user.get_self_info(credential)
        mid = self_info['mid']
        
        result = await dynamic.get_dynamic_page_info(credential=credential, host_mid=mid, pn=page)
        
        dynamics = []
        for item in result.get('items', []):
            dynamics.append({
                'dynamic_id': item.get('id_str'),
                'type': item.get('type'),
                'pub_time': item.get('modules', {}).get('module_author', {}).get('pub_time')
            })
        
        return {
            "success": True,
            "dynamics": dynamics
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


async def get_user_dynamics(mid: int, page: int = 1):
    """获取指定用户动态"""
    try:
        from bilibili_api import dynamic
        
        credential = load_credential()
        result = await dynamic.get_dynamic_page_info(credential=credential, host_mid=mid, pn=page)
        
        dynamics = []
        for item in result.get('items', []):
            dynamics.append({
                'dynamic_id': item.get('id_str'),
                'type': item.get('type'),
                'pub_time': item.get('modules', {}).get('module_author', {}).get('pub_time')
            })
        
        return {
            "success": True,
            "dynamics": dynamics
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


async def delete_dynamic(dynamic_id: int):
    """删除动态"""
    credential = load_credential()
    if not credential:
        return {"success": False, "error": "未登录，请先扫码登录"}
    
    try:
        from bilibili_api import dynamic
        
        d = dynamic.Dynamic(dynamic_id=dynamic_id, credential=credential)
        await d.delete()
        
        return {
            "success": True,
            "message": "动态删除成功"
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


# ==================== 热门/排行榜 ====================

async def get_hot_videos(pn: int = 1):
    """获取热门视频"""
    try:
        from bilibili_api import hot
        
        result = await hot.get_hot_videos(pn=pn)
        
        videos = []
        for item in result.get('list', []):
            videos.append({
                'bvid': item.get('bvid'),
                'title': item.get('title'),
                'author': item.get('owner', {}).get('name'),
                'play': item.get('stat', {}).get('view'),
                'like': item.get('stat', {}).get('like'),
                'desc': item.get('desc', '')[:100]
            })
        
        return {
            "success": True,
            "page": pn,
            "videos": videos
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


async def get_rank(type_name: str = "All", day: int = 3):
    """
    获取排行榜
    type_name: 排行榜类型枚举名，如 All, Douga, Music, Dance, Game, Knowledge, Technology,
               Sports, Car, Life, Food, Animal, Kichiku, Fashion, Ent, Cinephile,
               Original, Rookie, Bangumi, GuochuangAnime, Guochuang, Documentary, Movie, TV, Variety
    day: 时间范围，3=三日，7=一周（仅对番剧/电影等 PGC 类型有效）
    """
    try:
        from bilibili_api import rank

        type_map = {t.name: t for t in rank.RankType}
        rank_type = type_map.get(type_name, rank.RankType.All)
        day_type = rank.RankDayType.WEEK if day == 7 else rank.RankDayType.THREE_DAY
        result = await rank.get_rank(type_=rank_type, day=day_type)
        
        videos = []
        for item in result.get('list', [])[:20]:
            videos.append({
                'rank': item.get('rank'),
                'bvid': item.get('bvid'),
                'title': item.get('title'),
                'author': item.get('owner', {}).get('name'),
                'play': item.get('stat', {}).get('view'),
                'score': item.get('score')
            })
        
        return {
            "success": True,
            "type": type_name,
            "day": day,
            "videos": videos
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


async def get_weekly_hot(week: int = 0):
    """获取每周必看（B站精选）
    week: 期数，0 表示自动获取最新一期
    """
    try:
        from bilibili_api import hot

        if week <= 0:
            weeks_list = await hot.get_weekly_hot_videos_list()
            if not weeks_list.get('list'):
                return {"success": False, "error": "获取每周必看列表为空"}
            week = weeks_list['list'][0].get('number', 1)

        result = await hot.get_weekly_hot_videos(week=week)

        videos = []
        for item in result.get('list', []):
            videos.append({
                'bvid': item.get('bvid'),
                'title': item.get('title'),
                'author': item.get('owner', {}).get('name'),
                'play': item.get('stat', {}).get('view'),
                'like': item.get('stat', {}).get('like'),
                'rcmd_reason': item.get('rcmd_reason', '')
            })

        return {
            "success": True,
            "week": week,
            "videos": videos
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


# ==================== 直播相关 ====================

async def get_live_info(room_id: int):
    """获取直播间信息"""
    try:
        from bilibili_api import live
        
        room = live.LiveRoom(room_display_id=room_id)
        info = await room.get_room_info()
        
        room_info = info.get('room_info', {})
        anchor_info = info.get('anchor_info', {})
        
        return {
            "success": True,
            "room_id": room_info.get('room_id'),
            "title": room_info.get('title'),
            "live_status": room_info.get('live_status'),  # 0=未开播, 1=直播中, 2=轮播
            "area_name": room_info.get('area_name'),
            "online": room_info.get('online'),
            "anchor": {
                "uid": anchor_info.get('base_info', {}).get('uid'),
                "uname": anchor_info.get('base_info', {}).get('uname'),
                "fans": anchor_info.get('relation_info', {}).get('attention')
            }
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


async def get_live_area_list():
    """获取直播分区列表"""
    try:
        from bilibili_api import live_area

        result = await live_area.get_area_list()

        areas = []
        for category in result:
            sub_list = category.get('list', []) or []
            areas.append({
                'id': category.get('id'),
                'name': category.get('name'),
                'sub_areas': [{'id': sub.get('id'), 'name': sub.get('name')}
                             for sub in sub_list[:10]]
            })

        return {
            "success": True,
            "areas": areas
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


async def get_live_list(area_id: int, page: int = 1):
    """获取直播列表（按分区）
    area_id: 子分区 ID，可通过 get_live_area_list 获取
    """
    try:
        from bilibili_api import live_area

        credential = load_credential()
        result = await live_area.get_list_by_area(
            area_id=area_id, page=page, credential=credential
        )

        rooms = []
        for item in result.get('list', []) or []:
            rooms.append({
                'room_id': item.get('roomid'),
                'title': item.get('title'),
                'uname': item.get('uname'),
                'online': item.get('online'),
                'area_name': item.get('area_name')
            })

        return {
            "success": True,
            "page": page,
            "rooms": rooms
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


async def send_live_danmaku(room_id: int, text: str):
    """发送直播弹幕"""
    credential = load_credential()
    if not credential:
        return {"success": False, "error": "未登录，请先扫码登录"}
    
    try:
        from bilibili_api import live
        
        room = live.LiveRoom(room_display_id=room_id, credential=credential)
        await room.send_danmaku(live.Danmaku(text=text))
        
        return {
            "success": True,
            "message": "弹幕发送成功"
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


# ==================== 收藏夹管理 ====================

async def get_my_favorite_list():
    """获取我的收藏夹列表"""
    credential = load_credential()
    if not credential:
        return {"success": False, "error": "未登录，请先扫码登录"}
    
    try:
        from bilibili_api import favorite_list, user
        
        self_info = await user.get_self_info(credential)
        mid = self_info['mid']
        
        result = await favorite_list.get_video_favorite_list(uid=mid, credential=credential)
        
        folders = []
        for item in result.get('list', []):
            folders.append({
                'id': item.get('id'),
                'title': item.get('title'),
                'media_count': item.get('media_count'),
                'privacy': item.get('attr')  # 0=公开, 1=私密
            })
        
        return {
            "success": True,
            "folders": folders
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


async def get_favorite_content(media_id: int, page: int = 1):
    """获取收藏夹内容"""
    credential = load_credential()
    
    try:
        from bilibili_api import favorite_list
        
        result = await favorite_list.get_video_favorite_list_content(
            media_id=media_id, 
            page=page,
            credential=credential
        )
        
        videos = []
        for item in result.get('medias', []) or []:
            videos.append({
                'bvid': item.get('bvid'),
                'title': item.get('title'),
                'author': item.get('upper', {}).get('name'),
                'play': item.get('cnt_info', {}).get('play')
            })
        
        return {
            "success": True,
            "page": page,
            "has_more": result.get('has_more', False),
            "videos": videos
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


async def create_favorite_folder(title: str, intro: str = "", privacy: bool = False):
    """创建收藏夹"""
    credential = load_credential()
    if not credential:
        return {"success": False, "error": "未登录，请先扫码登录"}
    
    try:
        from bilibili_api import favorite_list
        
        result = await favorite_list.create_video_favorite_list(
            title=title,
            introduction=intro,
            private=privacy,
            credential=credential
        )
        
        return {
            "success": True,
            "media_id": result.get('id'),
            "message": f"收藏夹 '{title}' 创建成功"
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


# ==================== 关注/粉丝 ====================

async def follow_user(mid: int, unfollow: bool = False):
    """关注/取关用户"""
    credential = load_credential()
    if not credential:
        return {"success": False, "error": "未登录，请先扫码登录"}
    
    try:
        from bilibili_api import user
        
        u = user.User(uid=mid, credential=credential)
        if unfollow:
            await u.modify_relation(relation=user.RelationType.UNSUBSCRIBE)
            return {"success": True, "message": "取关成功"}
        else:
            await u.modify_relation(relation=user.RelationType.SUBSCRIBE)
            return {"success": True, "message": "关注成功"}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def get_my_followings(page: int = 1):
    """获取我的关注列表"""
    credential = load_credential()
    if not credential:
        return {"success": False, "error": "未登录，请先扫码登录"}
    
    try:
        from bilibili_api import user
        
        self_info = await user.get_self_info(credential)
        mid = self_info['mid']
        
        u = user.User(uid=mid, credential=credential)
        result = await u.get_followings(pn=page)
        
        users = []
        for item in result.get('list', []):
            users.append({
                'mid': item.get('mid'),
                'uname': item.get('uname'),
                'sign': item.get('sign', '')[:50]
            })
        
        return {
            "success": True,
            "page": page,
            "total": result.get('total', 0),
            "users": users
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


async def get_my_followers(page: int = 1):
    """获取我的粉丝列表"""
    credential = load_credential()
    if not credential:
        return {"success": False, "error": "未登录，请先扫码登录"}
    
    try:
        from bilibili_api import user
        
        self_info = await user.get_self_info(credential)
        mid = self_info['mid']
        
        u = user.User(uid=mid, credential=credential)
        result = await u.get_followers(pn=page)
        
        users = []
        for item in result.get('list', []):
            users.append({
                'mid': item.get('mid'),
                'uname': item.get('uname'),
                'sign': item.get('sign', '')[:50]
            })
        
        return {
            "success": True,
            "page": page,
            "total": result.get('total', 0),
            "users": users
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


# ==================== 历史记录 ====================

async def get_history(ps: int = 20, view_at: int = 0, max_oid: int = 0):
    """获取观看历史（新版 API）
    
    使用无限滚动方式获取历史记录。首次调用不需要传参数，
    后续调用需要传入上一次返回结果中某条记录的 view_at 和 oid 来获取更早的记录。
    
    Args:
        ps: 每页数量，默认 20
        view_at: 时间戳，获取此时间戳之前的历史记录，0 表示从最新开始
        max_oid: 历史记录截止目标 oid，0 表示不限制
    """
    credential = load_credential()
    if not credential:
        return {"success": False, "error": "未登录，请先扫码登录"}
    
    try:
        from bilibili_api import user
        
        # 使用新版 API
        kwargs = {
            'credential': credential,
            'ps': ps
        }
        if view_at > 0:
            kwargs['view_at'] = view_at
        if max_oid > 0:
            kwargs['max'] = max_oid
        
        result = await user.get_self_history_new(**kwargs)
        
        items = []
        cursor_info = {}
        
        # 解析历史记录列表
        for item in result.get('list', []):
            history = item.get('history', {})
            items.append({
                'oid': history.get('oid'),
                'bvid': history.get('bvid'),
                'business': history.get('business'),  # archive=视频, live=直播, article=专栏
                'title': item.get('title'),
                'author': item.get('author_name'),
                'author_mid': item.get('author_mid'),
                'progress': item.get('progress'),  # 观看进度（秒），-1 表示已看完
                'duration': item.get('duration'),
                'view_at': item.get('view_at'),  # 观看时间戳
                'cover': item.get('cover'),
                'tag_name': item.get('tag_name'),  # 分区名
            })
        
        # 提取游标信息，用于获取下一页
        if result.get('cursor'):
            cursor_info = {
                'max': result['cursor'].get('max', 0),
                'view_at': result['cursor'].get('view_at', 0),
                'business': result['cursor'].get('business', ''),
                'ps': result['cursor'].get('ps', ps)
            }
        
        return {
            "success": True,
            "items": items,
            "cursor": cursor_info,
            "has_more": len(items) >= ps
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


async def clear_history():
    """清空观看历史"""
    credential = load_credential()
    if not credential:
        return {"success": False, "error": "未登录，请先扫码登录"}
    
    try:
        from bilibili_api import user
        
        await user.clear_self_history(credential=credential)
        
        return {
            "success": True,
            "message": "历史记录已清空"
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


# ==================== 弹幕相关 ====================

async def get_video_danmaku(bvid: str, page_index: int = 0):
    """获取视频弹幕"""
    try:
        from bilibili_api import video, Danmaku
        
        v = video.Video(bvid=bvid)
        danmakus = await v.get_danmakus(page_index=page_index)
        
        result = []
        for dm in danmakus[:100]:  # 限制返回数量
            result.append({
                'text': dm.text,
                'time': dm.dm_time,  # 弹幕出现时间（秒）
                'mode': dm.mode,  # 1=滚动, 4=底部, 5=顶部
                'color': dm.color,
                'send_time': dm.send_time
            })
        
        return {
            "success": True,
            "count": len(danmakus),
            "danmakus": result
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


async def send_video_danmaku(bvid: str, text: str, dm_time: float = 0, page_index: int = 0):
    """发送视频弹幕
    
    Args:
        bvid: 视频 BV 号
        text: 弹幕内容
        dm_time: 弹幕出现的时间点（秒），默认为 0
        page_index: 分 P 序号，从 0 开始，默认为 0（第一个分 P）
    """
    credential = load_credential()
    if not credential:
        return {"success": False, "error": "未登录，请先扫码登录"}
    
    try:
        from bilibili_api import video, Danmaku
        
        v = video.Video(bvid=bvid, credential=credential)
        dm = Danmaku(text=text, dm_time=dm_time)
        await v.send_danmaku(page_index=page_index, danmaku=dm)
        
        return {
            "success": True,
            "message": "弹幕发送成功"
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


# ==================== 评论相关扩展 ====================

async def get_video_comments(bvid: str, page: int = 1):
    """获取视频评论"""
    credential = load_credential()
    
    try:
        from bilibili_api import video, comment
        
        v = video.Video(bvid=bvid)
        info = await v.get_info()
        aid = info['aid']
        
        result = await comment.get_comments(
            oid=aid,
            type_=comment.CommentResourceType.VIDEO,
            page_index=page,
            credential=credential
        )
        
        comments = []
        for item in result.get('replies', []) or []:
            comments.append({
                'rpid': item.get('rpid'),
                'content': item.get('content', {}).get('message'),
                'user': item.get('member', {}).get('uname'),
                'like': item.get('like'),
                'reply_count': item.get('rcount', 0),
                'time': item.get('ctime')
            })
        
        return {
            "success": True,
            "page": page,
            "total": result.get('page', {}).get('count', 0),
            "comments": comments
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


async def reply_comment(bvid: str, rpid: int, text: str):
    """回复评论"""
    credential = load_credential()
    if not credential:
        return {"success": False, "error": "未登录，请先扫码登录"}
    
    try:
        from bilibili_api import video, comment
        
        v = video.Video(bvid=bvid)
        info = await v.get_info()
        aid = info['aid']
        
        result = await comment.send_comment(
            text=text,
            oid=aid,
            type_=comment.CommentResourceType.VIDEO,
            root=rpid,
            credential=credential
        )
        
        return {
            "success": True,
            "rpid": result.get('rpid'),
            "message": "回复成功"
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


# ==================== 用户视频列表 ====================

async def get_user_videos(mid: int, page: int = 1, order: str = "pubdate"):
    """
    获取用户投稿视频
    order: pubdate=最新发布, click=最多播放, stow=最多收藏
    """
    try:
        from bilibili_api import user
        
        u = user.User(uid=mid)
        result = await u.get_videos(pn=page, order=user.VideoOrder(order))
        
        videos = []
        for item in result.get('list', {}).get('vlist', []):
            videos.append({
                'bvid': item.get('bvid'),
                'title': item.get('title'),
                'play': item.get('play'),
                'created': item.get('created'),
                'length': item.get('length')
            })
        
        return {
            "success": True,
            "page": page,
            "total": result.get('page', {}).get('count', 0),
            "videos": videos
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


# 工具映射
TOOLS = {
    # 账号管理
    'check_login': check_login,
    'get_login_qrcode': get_login_qrcode,
    'check_qrcode_status': lambda **kwargs: check_qrcode_status(),
    'logout': logout,
    
    # 内容发布
    'publish_dynamic': publish_dynamic,
    'upload_video': upload_video,
    'delete_dynamic': delete_dynamic,
    
    # 搜索
    'search_video': search_video,
    'search_user': search_user,
    
    # 视频信息
    'get_video_info': get_video_info,
    'get_user_info': get_user_info,
    'get_user_videos': get_user_videos,
    
    # 热门/排行
    'get_hot_videos': get_hot_videos,
    'get_rank': get_rank,
    'get_weekly_hot': get_weekly_hot,
    
    # 视频互动
    'like_video': like_video,
    'coin_video': coin_video,
    'favorite_video': favorite_video,
    'comment_video': comment_video,
    'get_video_comments': get_video_comments,
    'reply_comment': reply_comment,
    
    # 弹幕
    'get_video_danmaku': get_video_danmaku,
    'send_video_danmaku': send_video_danmaku,
    
    # 动态
    'like_dynamic': like_dynamic,
    'repost_dynamic': repost_dynamic,
    'get_my_dynamics': get_my_dynamics,
    'get_user_dynamics': get_user_dynamics,
    
    # 直播
    'get_live_info': get_live_info,
    'get_live_area_list': get_live_area_list,
    'get_live_list': get_live_list,
    'send_live_danmaku': send_live_danmaku,
    
    # 收藏夹
    'get_my_favorite_list': get_my_favorite_list,
    'get_favorite_content': get_favorite_content,
    'create_favorite_folder': create_favorite_folder,
    
    # 关注/粉丝
    'follow_user': follow_user,
    'get_my_followings': get_my_followings,
    'get_my_followers': get_my_followers,
    
    # 历史记录
    'get_history': get_history,
    'clear_history': clear_history,
}


async def main():
    if len(sys.argv) < 2:
        print("用法: python3 bili_call.py <tool_name> [json_args]")
        print(f"可用工具: {', '.join(TOOLS.keys())}")
        sys.exit(1)
    
    tool_name = sys.argv[1]
    
    if tool_name not in TOOLS:
        print(f"未知工具: {tool_name}")
        print(f"可用工具: {', '.join(TOOLS.keys())}")
        sys.exit(1)
    
    # 解析参数
    args = {}
    if len(sys.argv) > 2:
        try:
            args = json.loads(sys.argv[2])
        except json.JSONDecodeError as e:
            print(f"JSON 解析错误: {e}")
            sys.exit(1)
    
    # 调用工具
    tool_func = TOOLS[tool_name]
    result = await tool_func(**args)
    
    # 输出结果
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    asyncio.run(main())
