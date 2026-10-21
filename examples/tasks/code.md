在 examples/demo-workspace 对应的目标工作区中修改 greeting.py：

- greet(name) 对字符串先去除首尾空白，再返回 Hello, <name>!。
- 去空白后为空字符串时抛出 ValueError。
- 保持现有正常输入行为，并支持中文名字。
- 为正常输入、空白、空名字和中文名字添加单元测试。
- 使用 Python 标准库；不安装依赖、不发布、不调用外部服务。
- 验收：python3 -m unittest -v 全部通过，实际函数行为符合上述规则。
