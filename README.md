# ”江苏省第十五届大学生安全知识竞赛“脚本 2026

jiangsu-safety-competition

**🤔 食用指导**

如果您是普通用户，请直接下载右边的Release版本，右键，选择以管理员身份运行。

本程序分为带OCR和不带OCR两个版本，OCR版本适配性太差，暂时停更

使用OCR功能对Python版本有着严格的要求。

如果您是专业用户，以下提供方法以运行此脚本：

1.安装Python3，确保环境变量配置正确。

2.切换到程序目录，安装requirements.txt

```
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

3.运行主程序 main.py ，按照程序提示输入即可。

4.打包的话...非常的麻烦，要避免tqdm的爆炸问题，推荐使用以下命令：

```
pyinstaller --add-data "utils.py:." --add-data "database.db:." --add-data "dbProcess.py:." --add-data "donation.jpg:." --onefile --exclude-module pandas --exclude-module matplotlib --exclude-module IPython --exclude-module ipywidgets main.py
```

✒️ **进阶**

程序开发耗时较短，许多功能不完善，还请各位大佬谅解。

欢迎提交 Issue 来交换您的看法和对脚本的更多建议！

——南晓 Scwizard

😋 **饿饿 饭饭**

![donation](https://raw.githubusercontent.com/Scwizard/jiangsu-safety-competition/refs/heads/main/donation.jpg)
