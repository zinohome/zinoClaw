# Slack App Manifests — 芮通科技 ReTone Tech
# 使用方法：在 api.slack.com/apps → Create New App → From an app manifest
# 粘贴下面对应的 JSON，一次完成所有配置，然后 Install to Workspace 获取 Token

---

## 通用使用步骤（每个 App 重复）

1. 访问 https://api.slack.com/apps → **Create New App**
2. 选择 **"From an app manifest"**
3. 选择 Workspace → Next
4. 切换到 **JSON tab**，粘贴下面对应的 JSON
5. Next → Create
6. 左栏 **Socket Mode** → Enable → 生成 xapp- Token（⚠️ 立刻复制！只显示一次）
7. 左栏 **Install App** → Install to Workspace → xoxb- Token

---

## Dev-Lead（开远）— 已创建，待完成 Events 配置和安装

```json
{
  "display_information": {
    "name": "Dev-Lead",
    "description": "芮通科技 产品开发团队负责人 | 技术Lead",
    "background_color": "#B91C1C"
  },
  "features": {
    "bot_user": {
      "display_name": "Dev-Lead",
      "always_online": true
    },
    "assistant_view": {
      "assistant_description": "技术Lead，负责产品开发团队的任务拆解、协调和质量把关。"
    }
  },
  "oauth_config": {
    "scopes": {
      "bot": [
        "app_mentions:read",
        "assistant:write",
        "channels:history",
        "chat:write",
        "chat:write.public",
        "groups:history",
        "groups:read",
        "groups:write",
        "im:history",
        "im:read",
        "im:write",
        "mpim:history",
        "reactions:write",
        "users:read"
      ]
    }
  },
  "settings": {
    "event_subscriptions": {
      "bot_events": [
        "app_mention",
        "message.channels",
        "message.groups",
        "message.im",
        "message.mpim"
      ]
    },
    "interactivity": {
      "is_enabled": true
    },
    "org_deploy_enabled": false,
    "socket_mode_enabled": true,
    "token_rotation_enabled": false
  }
}
```

---

## Dev-PM（开策）

```json
{
  "display_information": {
    "name": "Dev-PM",
    "description": "芮通科技 产品经理 | 需求分析与PRD",
    "background_color": "#1D4ED8"
  },
  "features": {
    "bot_user": {
      "display_name": "Dev-PM",
      "always_online": true
    },
    "assistant_view": {
      "assistant_description": "产品经理，负责需求分析、用户故事和PRD编写。"
    }
  },
  "oauth_config": {
    "scopes": {
      "bot": [
        "app_mentions:read",
        "assistant:write",
        "channels:history",
        "chat:write",
        "chat:write.public",
        "groups:history",
        "groups:read",
        "groups:write",
        "im:history",
        "im:read",
        "im:write",
        "mpim:history",
        "reactions:write",
        "users:read"
      ]
    }
  },
  "settings": {
    "event_subscriptions": {
      "bot_events": [
        "app_mention",
        "message.channels",
        "message.groups",
        "message.im",
        "message.mpim"
      ]
    },
    "interactivity": {"is_enabled": true},
    "socket_mode_enabled": true,
    "token_rotation_enabled": false
  }
}
```

---

## Dev-Eng（开程）

```json
{
  "display_information": {
    "name": "Dev-Eng",
    "description": "芮通科技 全栈工程师 | 代码执行者",
    "background_color": "#065F46"
  },
  "features": {
    "bot_user": {
      "display_name": "Dev-Eng",
      "always_online": true
    },
    "assistant_view": {
      "assistant_description": "全栈工程师，负责代码编写、调试与执行。"
    }
  },
  "oauth_config": {
    "scopes": {
      "bot": [
        "app_mentions:read",
        "assistant:write",
        "channels:history",
        "chat:write",
        "chat:write.public",
        "groups:history",
        "groups:read",
        "groups:write",
        "im:history",
        "im:read",
        "im:write",
        "mpim:history",
        "reactions:write",
        "users:read"
      ]
    }
  },
  "settings": {
    "event_subscriptions": {
      "bot_events": [
        "app_mention",
        "message.channels",
        "message.groups",
        "message.im",
        "message.mpim"
      ]
    },
    "interactivity": {"is_enabled": true},
    "socket_mode_enabled": true,
    "token_rotation_enabled": false
  }
}
```

---

## Dev-QA（开验）

```json
{
  "display_information": {
    "name": "Dev-QA",
    "description": "芮通科技 质量官 | 代码审查与测试",
    "background_color": "#92400E"
  },
  "features": {
    "bot_user": {
      "display_name": "Dev-QA",
      "always_online": true
    },
    "assistant_view": {
      "assistant_description": "质量官，负责代码审查、测试验收和Bug发现。"
    }
  },
  "oauth_config": {
    "scopes": {
      "bot": [
        "app_mentions:read",
        "assistant:write",
        "channels:history",
        "chat:write",
        "chat:write.public",
        "groups:history",
        "groups:read",
        "groups:write",
        "im:history",
        "im:read",
        "im:write",
        "mpim:history",
        "reactions:write",
        "users:read"
      ]
    }
  },
  "settings": {
    "event_subscriptions": {
      "bot_events": [
        "app_mention",
        "message.channels",
        "message.groups",
        "message.im",
        "message.mpim"
      ]
    },
    "interactivity": {"is_enabled": true},
    "socket_mode_enabled": true,
    "token_rotation_enabled": false
  }
}
```

---

## Res-Lead（博远）

```json
{
  "display_information": {
    "name": "Res-Lead",
    "description": "芮通科技 研究咨询团队负责人 | 研究Lead",
    "background_color": "#1E40AF"
  },
  "features": {
    "bot_user": {
      "display_name": "Res-Lead",
      "always_online": true
    },
    "assistant_view": {
      "assistant_description": "研究负责人，制定研究框架，统筹团队，向CEO汇报研究结论。"
    }
  },
  "oauth_config": {
    "scopes": {
      "bot": [
        "app_mentions:read",
        "assistant:write",
        "channels:history",
        "chat:write",
        "chat:write.public",
        "groups:history",
        "groups:read",
        "groups:write",
        "im:history",
        "im:read",
        "im:write",
        "mpim:history",
        "reactions:write",
        "users:read"
      ]
    }
  },
  "settings": {
    "event_subscriptions": {
      "bot_events": [
        "app_mention",
        "message.channels",
        "message.groups",
        "message.im",
        "message.mpim"
      ]
    },
    "interactivity": {"is_enabled": true},
    "socket_mode_enabled": true,
    "token_rotation_enabled": false
  }
}
```

---

## Res-Deep（博研）

```json
{
  "display_information": {
    "name": "Res-Deep",
    "description": "芮通科技 深度研究员 | 网络深度检索",
    "background_color": "#312E81"
  },
  "features": {
    "bot_user": {
      "display_name": "Res-Deep",
      "always_online": true
    },
    "assistant_view": {
      "assistant_description": "深度研究员，执行网络深度检索，产出高质量原始研究资料。"
    }
  },
  "oauth_config": {
    "scopes": {
      "bot": [
        "app_mentions:read",
        "assistant:write",
        "channels:history",
        "chat:write",
        "chat:write.public",
        "groups:history",
        "groups:read",
        "groups:write",
        "im:history",
        "im:read",
        "im:write",
        "mpim:history",
        "reactions:write",
        "users:read"
      ]
    }
  },
  "settings": {
    "event_subscriptions": {
      "bot_events": [
        "app_mention",
        "message.channels",
        "message.groups",
        "message.im",
        "message.mpim"
      ]
    },
    "interactivity": {"is_enabled": true},
    "socket_mode_enabled": true,
    "token_rotation_enabled": false
  }
}
```

---

## Res-Insight（博析）

```json
{
  "display_information": {
    "name": "Res-Insight",
    "description": "芮通科技 行业分析师 | 竞品分析与市场数据",
    "background_color": "#0F766E"
  },
  "features": {
    "bot_user": {
      "display_name": "Res-Insight",
      "always_online": true
    },
    "assistant_view": {
      "assistant_description": "行业分析师，负责竞品对比、市场数据和结构化洞察。"
    }
  },
  "oauth_config": {
    "scopes": {
      "bot": [
        "app_mentions:read",
        "assistant:write",
        "channels:history",
        "chat:write",
        "chat:write.public",
        "groups:history",
        "groups:read",
        "groups:write",
        "im:history",
        "im:read",
        "im:write",
        "mpim:history",
        "reactions:write",
        "users:read"
      ]
    }
  },
  "settings": {
    "event_subscriptions": {
      "bot_events": [
        "app_mention",
        "message.channels",
        "message.groups",
        "message.im",
        "message.mpim"
      ]
    },
    "interactivity": {"is_enabled": true},
    "socket_mode_enabled": true,
    "token_rotation_enabled": false
  }
}
```

---

## Res-Write（博文）

```json
{
  "display_information": {
    "name": "Res-Write",
    "description": "芮通科技 内容撰稿人 | 报告润色与专业写作",
    "background_color": "#701A75"
  },
  "features": {
    "bot_user": {
      "display_name": "Res-Write",
      "always_online": true
    },
    "assistant_view": {
      "assistant_description": "内容撰稿人，将研究结论转化为高质量报告、提案和演讲稿。"
    }
  },
  "oauth_config": {
    "scopes": {
      "bot": [
        "app_mentions:read",
        "assistant:write",
        "channels:history",
        "chat:write",
        "chat:write.public",
        "groups:history",
        "groups:read",
        "groups:write",
        "im:history",
        "im:read",
        "im:write",
        "mpim:history",
        "reactions:write",
        "users:read"
      ]
    }
  },
  "settings": {
    "event_subscriptions": {
      "bot_events": [
        "app_mention",
        "message.channels",
        "message.groups",
        "message.im",
        "message.mpim"
      ]
    },
    "interactivity": {"is_enabled": true},
    "socket_mode_enabled": true,
    "token_rotation_enabled": false
  }
}
```
