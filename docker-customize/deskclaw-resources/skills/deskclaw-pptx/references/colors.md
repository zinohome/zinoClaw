# Design System

## Color Palette Reference

| # | Name | Colors | Style | Use Cases | Tips |
|---|------|--------|-------|-----------|------|
| 1 | Modern & Wellness | `#006d77` `#83c5be` `#edf6f9` `#ffddd2` `#e29578` | Fresh, soothing | Healthcare, counseling, skincare, yoga/spa | Deep teal for titles, light pink for background |
| 2 | Business & Authority | `#2b2d42` `#8d99ae` `#edf2f4` `#ef233c` `#d90429` | Formal, classic | Annual reports, financial analysis, corporate intro, government | Deep blue for professionalism, bright red to highlight data |
| 3 | Nature & Outdoors | `#606c38` `#283618` `#fefae0` `#dda15e` `#bc6c25` | Grounded, earthy | Outdoor gear, environmental, agriculture, historical culture | Dark green base, cream text |
| 4 | Vintage & Academic | `#780000` `#c1121f` `#fdf0d5` `#003049` `#669bbc` | Classic, scholarly | Academic lectures, history reviews, museums, heritage brands | Strong contrast between deep red and deep blue |
| 5 | Soft & Creative | `#cdb4db` `#ffc8dd` `#ffafcc` `#bde0fe` `#a2d2ff` | Dreamy, candy-toned | Mother & baby, desserts, women's fashion, kindergarten | Use dark gray or black for text |
| 6 | Bohemian | `#ccd5ae` `#e9edc9` `#fefae0` `#faedcd` `#d4a373` | Gentle, muted | Wedding planning, home decor, organic food, slow living | Cream background, green-brown accents |
| 7 | Vibrant & Tech | `#8ecae6` `#219ebc` `#023047` `#ffb703` `#fb8500` | High energy, sporty | Sports events, gyms, startup pitches, youth education | Deep blue for stability, orange as focal accent |
| 8 | Craft & Artisan | `#7f5539` `#a68a64` `#ede0d4` `#656d4a` `#414833` | Rustic, coffee-toned | Coffee shops, handicrafts, traditional culture, bakery | Suited for paper/leather textures |
| 9 | Tech & Night | `#000814` `#001d3d` `#003566` `#ffc300` `#ffd60a` | Deep, luminous | Tech launches, astronomy, night economy, luxury automobiles | Must use dark mode |
| 10 | Education & Charts | `#264653` `#2a9d8f` `#e9c46a` `#f4a261` `#e76f51` | Clear, logical | Statistical reports, education, market analysis, general business | Perfect chart color scheme |
| 11 | Forest & Eco | `#dad7cd` `#a3b18a` `#588157` `#3a5a40` `#344e41` | Monochrome gradient, forest | Landscape design, ESG reports, environmental causes, botanical | Monochrome palette is safe and cohesive |
| 12 | Elegant & Fashion | `#edafb8` `#f7e1d7` `#dedbd2` `#b0c4b1` `#4a5759` | Muted, Morandi tones | Haute couture, art galleries, beauty brands, magazine style | Negative space is key |
| 13 | Art & Food | `#335c67` `#fff3b0` `#e09f3e` `#9e2a2b` `#540b0e` | Rich, vintage-poster | Food documentaries, art exhibitions, ethnic themes, vintage restaurants | Works well with large color blocks |
| 14 | Luxury & Mysterious | `#22223b` `#4a4e69` `#9a8c98` `#c9ada7` `#f2e9e4` | Cool, purple-toned | Jewelry showcases, hotel management, high-end consulting, psychology | Purple evokes premium atmosphere |
| 15 | Pure Tech Blue | `#03045e` `#0077b6` `#00b4d8` `#90e0ef` `#caf0f8` | Futuristic, clean | Cloud/AI, water/ocean, hospitals, clean energy | Deep ocean to sky gradient |
| 16 | Coastal Coral | `#0081a7` `#00afb9` `#fdfcdc` `#fed9b7` `#f07167` | Refreshing, summery | Travel, summer events, beverage brands, ocean themes | Teal and coral as complementary focal colors |
| 17 | Vibrant Orange Mint | `#ff9f1c` `#ffbf69` `#ffffff` `#cbf3f0` `#2ec4b6` | Bright, cheerful | Children's events, promotional posters, FMCG, social media | Orange grabs attention, mint feels fresh |
| 18 | Platinum White Gold | `#0a0a0a` `#0070F3` `#D4AF37` `#f5f5f5` `#ffffff` | Premium, professional | Agent products, corporate websites, fintech, luxury brands | White-gold base, blue for action, gold for emphasis |


## Color Palette Rules (MANDATORY)

### Strict Palette Adherence

**Use ONLY the provided color palette. Do NOT create or modify colors.**

- All colors must come from the user-provided palette
- Do NOT use colors outside the palette
- Do NOT modify palette colors (brightness, saturation, mixing)
- **Only exception**: Add transparency using the `transparency` property (0-100)

```javascript
// Correct: Using palette colors
slide.addShape(pres.shapes.RECTANGLE, { fill: { color: theme.primary } });
slide.addText("Title", { color: theme.accent });

// Wrong: Colors outside palette
slide.addShape(pres.shapes.RECTANGLE, { fill: { color: "1a1a2e" } });
```

### No Gradients

**Gradients are prohibited. Use solid colors only.**

### No Animations

**Animations and transitions are prohibited.** All slides must be static.

