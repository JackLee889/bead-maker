# 拼豆图生成器

这是一个在浏览器里操作的 Python 程序。图片只在运行程序的电脑上处理，不会上传到外部服务器。

## 功能

- 上传 JPG、PNG、WEBP、BMP、TIFF、GIF，安装 `pillow-heif` 后支持 HEIC/HEIF
- 自定义横向/纵向拼豆数量、单颗尺寸、裁剪方式、对比度和饱和度
- 内置 32 色、64 色通用屏幕参考色库
- 自动从原画提取 2–64 种颜色
- 导入带品牌和色号的 CSV，可从同一文件中选择指定品牌
- 采用 Lab 感知色差，而不是简单的 RGB 距离匹配
- 处理前后预览、带色号彩色网格、颜色用量统计
- 导出 PNG、UTF-8 CSV、Excel（XLSX）、A4 分页 PDF 和完整 ZIP 图纸包

## Excel 像素图导出

生成拼豆图后，进入“下载”，点击“下载像素单元格图（Excel）”。完整 ZIP 也包含 `bead_pattern.xlsx`。

- “拼豆图”工作表：转换后的一个像素对应一个真实单元格，左上角从 A1 开始。例如 40 × 25 颗对应 40 列、25 行，不是将 PNG 图片插入 Excel。
- 单元格使用匹配后的拼豆颜色填充，近似正方形，每 5 格加粗边界。字体或显示缩放不同可能产生轻微宽高差异。
- 生成时勾选“格子内显示色号”，Excel 内也会居中显示完整色号，长色号缩小显示；取消勾选则只保留色块。
- “色号统计”工作表保留品牌、色号、名称、HEX 和数量。数量是生成时的快照，手工修改图格后不会自动重新统计。
- 网格不包含 PNG 预览放大产生的额外像素、坐标装饰或外边距；最大为 300 × 300 个单元格。
- 如需清晰的分页制作图纸，优先使用现有 A4 PDF 导出。

升级已有安装后，请运行 `python -m pip install -r requirements.txt` 并重启程序；旧会话需要重新生成图纸。

## Windows 安装与运行

### 推荐：一键本地部署

1. 安装 Python 3.10 或更高版本，安装时勾选 **Add python.exe to PATH**。
2. 解压完整程序包；不要直接在 ZIP 压缩包预览窗口中运行。
3. 双击 `start_windows.bat`。
4. 第一次启动会创建 `.venv` 并下载依赖，完成后浏览器自动打开 `http://127.0.0.1:8501`。
5. 保持黑色命令窗口开启；关闭窗口即停止程序。以后仍双击同一个脚本启动。

`127.0.0.1` 只允许当前电脑访问。首次安装依赖需要联网；依赖安装完毕后，图片转换和文件导出不调用外部图片处理服务。

### Windows 手工部署

在本文件夹打开命令提示符：

```bat
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

程序会自动打开浏览器。以后再次使用时，只需进入本文件夹并运行：

```bat
.venv\Scripts\activate
python -m streamlit run app.py
```

也可以在终端运行 `./start_macos_linux.sh`。

如果浏览器没有自动打开，请手动访问 `http://127.0.0.1:8501`。如果提示端口被占用，请先关闭之前打开的拼豆图命令窗口，再重新运行。

## macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

## 下载源码并启动调试（Windows / VS Code）

1. 下载并完整解压源码包，使用 VS Code 打开解压后的 `bead_maker` 文件夹。
2. 安装 VS Code 的 Python 与 Python Debugger 扩展。
3. 先双击 `start_windows.bat` 一次，或在终端运行 `.venv\Scripts\python.exe -m pip install -r requirements-dev.txt`。
4. 在 VS Code 左侧打开“运行和调试”，选择 **Debug Bead Maker (F5)**，按 F5。
5. 可在 `app.py`、`core.py`、`excel_export.py` 中设置断点。浏览器地址为 `http://127.0.0.1:8501`；按 Shift+F5 停止。

另一种方式是双击 `debug_windows.bat`。它会启动网页并在 `127.0.0.1:5678` 等待调试器附加；随后在 VS Code 中选择 **Attach to debug_windows.bat** 并按 F5。调试脚本默认不暂停等待附加，因此即使暂时不连接调试器，网页也能正常启动。

常用断点位置：

- `app.py`：生成按钮后的图像处理和下载结果组装。
- `core.py`：`prepare_image()`、`map_to_palette()`、`make_pdf()`。
- `excel_export.py`：`make_xlsx()`，检查一像素一单元格的映射。

运行回归测试：

```bat
.venv\Scripts\python.exe test_core.py
.venv\Scripts\python.exe -m unittest test_excel -v
.venv\Scripts\python.exe test_app.py
```

## 在 Codex 中继续开发

源码包已经按 Git 项目整理，并包含 `AGENTS.md`，Codex 会据此识别项目结构、测试命令和必须保持的导出规则。

在 ChatGPT Windows 桌面应用中切换到 **Codex**，选择打开本地项目，然后选中解压后的 `bead_maker` 文件夹。选择 **Local** 可直接操作当前源码；需要隔离并行开发时可选择 **Worktree**。依赖尚未安装时，先在集成终端运行 `start_windows.bat`，或将 `python -m pip install -r requirements-dev.txt` 配置为本地环境的 Setup 脚本。

Codex 云端不能直接读取电脑上的文件夹。若要从网页使用云端任务，需要先把此 Git 仓库推送到你自己的 GitHub 或 GitLab，再在 Codex 中连接该仓库并创建环境。

## 品牌色号表格式

点击网页中的“下载 CSV 色号表模板”，或参考 `sample_palette.csv`：

```csv
brand,code,name,hex
我的品牌,A01,白色,#FFFFFF
我的品牌,A02,黑色,#18191C
```

也可以不用 `hex`，改为 `r,g,b` 三列：

```csv
brand,code,name,r,g,b
我的品牌,A01,白色,255,255,255
我的品牌,A02,黑色,24,25,28
```

- `brand`/`品牌`：品牌名；一个 CSV 可以包含多个品牌
- `code`/`色号`：显示在拼豆格子里的编号
- `name`/`名称`：颜色名称
- `hex`：六位 RGB 屏幕色，例如 `#FF0000`

实体拼豆、显示器和照片的颜色会有差异。追求准确时，建议在固定光线下实拍自己的拼豆色卡并测量 RGB，再导入程序。

## 使用建议

- 人像从宽 60–100 颗开始，复杂画作从宽 100–160 颗开始。
- 实际制作通常不要开启过多颜色；24–40 色比较容易购买和整理。
- A4 打印默认 25 × 35 格一页，色号最清楚；需要省纸时可选择 40 × 55。
- 5 mm 拼豆的成品宽度约为“横向颗数 × 0.5 cm”。
