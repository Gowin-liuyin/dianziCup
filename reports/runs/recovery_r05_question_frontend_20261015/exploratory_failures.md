# 实施中探索失败（工具输出摘录）

这些命令发生在正式runner采样前。这里只保存真实工具输出摘录及已知信息，不冒称完整原始stdout，也不补造缺失时间。

1. cwd `D:/dianzi-wt-r05-question-frontend/frontend`，命令 `npm run test -- --run src/api/question-contracts.test.ts src/api/question-client.test.ts src/features/questions/question-workspace.test.tsx`。Vitest开始16:48:33，报告duration2.89s；工具exit1，三个文件70项断言通过但有1 unhandled error：`TypeError: document.getElementById(...)?.scrollIntoView is not a function`。属于jsdom缺少该DOM API，不是业务证据失败；沿用既有事件抽屉`scrollIntoView?.`兼容写法。后续249项全回归通过，浏览器实际scroll/focus通过。

2. cwd误写为仓库根 `D:/dianzi-wt-r05-question-frontend` 的 `npm run typecheck` 与 `npm run lint` 均未找到根package.json，输出`ENOENT ... D:\dianzi-wt-r05-question-frontend\package.json`，工具exit1。没有执行类型或lint业务检查，不计为通过或业务失败。此轮未采精确开始结束；后续正式runner固定frontend cwd。

3. 正式首轮typecheck在`typecheck.command.json`记录exit2；`typecheck.log`保留两个真实类型错误：unknown对象未通过Record type guard；Testing Library ByRoleOptions不含exact。补充明确type guard、删无效测试选项后通过，未用cast/Any/ignore。

没有删测试、改金标/门槛/分母、把失败改skip。未执行live模型请求。
