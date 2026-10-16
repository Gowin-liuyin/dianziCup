# 本run原字节保存记录

限定范围：仅本目录`.gitattributes`，没有改全局attributes、产品、测试规则或评分门。

`* -text`保证Git不改证据换行；log/xml/txt使用`-diff`以保存并核hash的原输出作为审查材料。Python、JSON与其他可审源文件仍正常显示diff。`whitespace=trailing-space,space-before-tab,cr-at-eol`保留实际空白检查，仅承认Windows合法CRLF。

初次raw重存后diff检查exit2，将JSON文本行末CR当trailing whitespace；原输出完整保存为`raw_diffcheck_red.log`。增加本目录cr-at-eol后相同diff命令exit0，见`raw_diffcheck_green.log`。没有以修改代码或测试规避业务错误。

外部报告正文继续现有Git-LF合同，精确原字节另保存在`report_raw.md.gz`；正文raw SHA/Git filtered blob分别在report_write_receipt中。manifest对正文另列git_lf_sha256/exact_raw_copy，跨工作树审查应解压原副本核raw，或对正文规范LF后核Git视图。

最终actual material commit由实际Git结果单独交接，收据不虚构自引用commit/hash。
