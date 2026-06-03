# 表情包目录

把表情包图片文件放在本目录，后端会自动选用，URL 形如 `/static/stickers/<文件名>`。

## 命名约定

- 支持的格式：`.png` `.jpg` `.jpeg` `.gif` `.webp`
- 文件名建议包含「情绪(mood)」或「关键词(keyword)」，例如：
  - `庆祝.png`
  - `震惊.gif`
  - `无语_躺平.png`
- 选图逻辑（见 `app/finance_agent/sticker_agent.py` 的 `resolve_sticker_url`）：
  1. 先按 `mood`、再按 `keyword` 在文件名中做包含匹配；
  2. 没命中则在本目录随机挑一张；
  3. 本目录为空时回退到占位图（placehold.co）。

放入真实图片后，无需改代码即可生效。
