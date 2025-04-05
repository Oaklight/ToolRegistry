# OpenAPI 示例服务器

[English](README_en)

该服务器是一个 OpenAPI 示例服务器，提供基本的算术运算（加、减、乘、除）的 OpenAPI 接口。这是一个示例实现，供学习和参考使用。

## 运行服务器

要运行服务器，请执行：

    python main.py

程序会从环境变量 `PORT` 中读取运行端口，如未设置，则默认使用端口 `8000`。

## 安装依赖

通过以下命令安装所需依赖：

    pip install -r requirements.txt

## 访问服务

服务器启动后，可以通过以下地址访问：

    http://localhost:8000

（若设置了自定义端口，请将 `8000` 替换为相应的端口号。）
