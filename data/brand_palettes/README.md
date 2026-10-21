# 内置品牌色卡数据

此目录提供可离线使用的品牌色号与 RGB 数据，运行程序时不会从网络下载。数据来自 [HansBug/pindou-color-data](https://github.com/HansBug/pindou-color-data/tree/178dafbc9e77d3de556550dbd058270200129186)，固定上游提交为 `178dafbc9e77d3de556550dbd058270200129186`，各文件的数据日期为 2026-05-19。

这些是公开整理的屏幕参考色，不能视为品牌官方实测色值或完整在售清单。实体拼豆、显示器、拍摄光线会有差异；数据不用于推断产品直径、软硬度或特殊材质效果。

## 文件与来源

JSON 文件是所列提交对应 `colors.json` 的原始快照，未修改内容。

| 本地文件 | 原始记录数 | 参与配色 | 原始文件 |
| --- | ---: | ---: | --- |
| `mard-221-github.json` | 221 | 221 | [MARD 221](https://github.com/HansBug/pindou-color-data/blob/178dafbc9e77d3de556550dbd058270200129186/mard-221-github/colors.json) |
| `mard-291-github.json` | 291 | 291 | [MARD 291](https://github.com/HansBug/pindou-color-data/blob/178dafbc9e77d3de556550dbd058270200129186/mard-291-github/colors.json) |
| `coco-291.json` | 291 | 291 | [COCO 291](https://github.com/HansBug/pindou-color-data/blob/178dafbc9e77d3de556550dbd058270200129186/coco-291/colors.json) |
| `manman-278.json` | 278 | 278 | [漫漫 278](https://github.com/HansBug/pindou-color-data/blob/178dafbc9e77d3de556550dbd058270200129186/manman-278/colors.json) |
| `panpan-289.json` | 289 | 285 | [盼盼 289](https://github.com/HansBug/pindou-color-data/blob/178dafbc9e77d3de556550dbd058270200129186/panpan-289/colors.json) |
| `mixiaowo-290.json` | 290 | 286 | [咪小窝 290](https://github.com/HansBug/pindou-color-data/blob/178dafbc9e77d3de556550dbd058270200129186/mixiaowo-290/colors.json) |

MARD 采用同源的 221/291 版本，已有色号的 RGB 保持一致。盼盼和咪小窝各包含 4 条未确认色号，加载器会排除这些记录，避免把占位编号用于制作和采购。分组沿用数据中的 `group` 字段，不自行将其解释为材质或规格。

## 许可与导出

原始数据遵循 [MIT License](LICENSE)，版权声明为 `Copyright (c) 2026 HansBug`。本目录保留完整原始许可。随应用发布时必须包含这些 JSON 文件和许可；品牌模式生成的 ZIP 也附带来源、数据 SHA-256 及许可文本。

`settings.json` 记录所选品牌、版本、分组、固定上游提交和实际数据文件的校验值。`palette_used.csv` 保存本次参与匹配的色库，`bead_usage.csv` 保存实际用量。图片及导出处理均在本机完成。

## 更新约定

更新色卡时，应核对上游来源、许可、日期及色号变化，再替换固定版本快照并更新 `brand_palettes.py` 中的来源提交、目录和相关测试。重新检查有效记录数、排除项、同源版本的 RGB 一致性，并运行项目规定的三组回归测试。不添加启动时自动联网更新。
