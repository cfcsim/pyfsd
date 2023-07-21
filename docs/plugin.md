# 插件使用
一般地，只需要创建pyfsd/plugins目录然后把插件文件丢进去就行。
以wheel形式安装时需要用`PYTHONPATH=. twistd -n pyfsd`来启动PyFSD，不然不能加载插件。
