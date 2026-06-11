# NVIDIA 生态链完整研究框架：从道法器到术前检查

这份文件的目标不是给买卖建议，而是把今天的思路固化成一个可复用研究系统。

## 1. 道：为什么这条链值得研究

NVIDIA 生态链的本质不是普通供应链，而是 AI factory 的生产资料体系。NVIDIA 控制 GPU、网络、软件栈、生态标准和客户路径；第一层供应商则控制 HBM、先进封装、光互联、电源、散热、服务器等物理瓶颈。

所以这条链的投资逻辑类似当年的果链：

```text
巨无霸定义需求和生态
关键供应商吃到订单弹性
小盘瓶颈件股价波动大于巨无霸本体
```

但 NVIDIA 链比果链更强的一点是：AI factory 早期存在更多硬瓶颈，部分供应商有短期涨价和扩利润能力；也更危险的一点是：涨幅太快后，估值已经把未来好几年订单提前买进去。

## 2. 法：三类公司不要混在一起看

| 类型 | 代表 | 核心问题 | 看错的风险 |
|---|---|---|---|
| 真瓶颈 | HBM、TSMC/CoWoS、Broadcom、Marvell、光模块、电源液冷 | 供给是否紧、毛利是否守得住 | 涨太多后，业绩只要不超预期就回撤 |
| 强配套 | Dell、HPE、ODM、封测、制造服务 | 订单能否转成利润和现金流 | 把收入增长误读成利润增长 |
| 第二层客户 | 云厂商、AI 云、主权 AI、汽车/机器人伙伴 | capex 能否转成收入和利润 | 它们可能只是替 NVIDIA 买单 |

## 3. 器：核心评分模型

机会分：

```text
订单联动 + 瓶颈程度 + 议价权 + 订单能见度
```

风险分：

```text
估值热度 + 替代/过剩风险 + 利润穿透风险
```

读取方式：

| 组合 | 含义 | 操作含义 |
|---|---|---|
| 高机会 + 低风险 | 最值得长期跟踪 | 可进入核心池 |
| 高机会 + 高风险 | 好公司但可能太热 | 只等回撤/业绩再确认 |
| 中机会 + 中风险 | 配套型标的 | 看毛利、现金流、客户集中 |
| 低机会 + 高风险 | 概念扩散 | 原则上不碰 |

完整 scorecard 在 [nvidia-ecosystem-scorecard-2026.csv](/Volumes/PortableSSD/Projects/Claude_Projects/投资思考/nvidia-ecosystem-scorecard-2026.csv)。

## 4. 当前分层结论

### 第一梯队：基本面硬度最高

| 公司 | 环节 | 为什么硬 | 最大问题 |
|---|---|---|---|
| TSMC | 先进制程 + CoWoS | AI 芯片制造和封装底座，替代难 | 体量大，弹性不如小票 |
| SK Hynix | HBM | HBM 纯度高，直接卡 NVIDIA/AI GPU 放量 | 已暴涨，后续看 HBM ASP 和份额 |
| Broadcom | ASIC + AI networking | 定制 AI 芯片和网络芯片双受益 | 估值不低，客户集中 |
| NVIDIA | 生态锚点 | 控制标准、软件栈和最高利润环节 | 市场要求它长期超级好 |

### 第二梯队：机会强，但需要等业绩穿透

| 公司 | 环节 | 机会 | 必查点 |
|---|---|---|---|
| Marvell | AI 互联 + 定制芯片 | AI bookings 强，收入弹性大 | bookings 能否变成 FCF |
| Coherent | 光器件/光通信 | AI datacenter 光互联需求强 | 产品结构、毛利和债务 |
| Lumentum | 光模块/激光器 | 高速光互联高弹性 | 涨幅过大，ASP 和订单取消风险 |
| Vertiv | 电源/液冷 | 数据中心供电散热硬需求 | backlog 执行、产能和毛利 |
| Delta Electronics | 电源/热管理 | AI server power/thermal 受益明显 | 涨幅巨大，估值已重估 |
| Arista | AI 网络设备 | 以太网 AI fabric 受益 | 大客户集中，估值要求高 |
| Micron | HBM/存储 | HBM + 数据中心存储周期弹性 | 存储周期本身波动大 |

### 第三梯队：订单强，但容易只赚辛苦钱

| 公司 | 环节 | 为什么不能只看订单 |
|---|---|---|
| Dell | AI server | Q1 FY2027 AI orders 和 AI server revenue 很强，但服务器硬件毛利率低 |
| HPE | AI server/network | 收入弹性强，但利润穿透要验证 |
| 鸿海/广达/纬创/纬颖 | ODM | AI 服务器订单清晰，但制造商容易被压价 |
| Fabrinet/ASE/Amkor | 制造/封测服务 | 受益需求，但议价权通常弱于瓶颈器件 |

### 特别观察：第二层客户

云厂商不是简单受益者。它们购买 NVIDIA 算力，短期是 capex，长期才可能变成利润。

| 公司 | 关键问题 |
|---|---|
| Microsoft | Copilot/Azure AI 能否覆盖 capex 和折旧 |
| Alphabet | AI 能否增强 Search/Cloud，而不是削弱搜索广告 |
| Amazon | AWS AI 收入和利润率能否重新加速 |
| Meta | AI 推荐和广告 ROI 能否覆盖巨额 capex |
| Oracle | AI cloud backlog 质量、债务和数据中心投资能否匹配 |
| CoreWeave/Nebius | 利用率、债务、折旧和客户集中是生命线 |

## 5. 最新披露信号

这些不是完整估值模型，只是证明“AI factory 需求确实在进入财报”的证据锚点：

| 公司 | 最新信号 | 解释 |
|---|---|---|
| Broadcom | Q1 FY2026 AI revenue 84 亿美元，同比 +106% | AI custom accelerators + AI networking 是真实收入，不只是概念 |
| Dell | Q1 FY2027 AI orders 244 亿美元，AI server revenue 161 亿美元 | 服务器订单很强，但还要看利润率和现金流 |
| Vertiv | Q1 FY2026 上调全年指引；此前 backlog 达 150 亿美元 | 数据中心电源/散热需求强，但执行压力大 |
| Marvell | Q1 FY2027 披露 AI-related bookings 强，并上调 FY2027/FY2028 revenue outlook | 关键看 bookings 转收入和利润 |
| Coherent | Q3 FY2026 revenue 18.1 亿美元，Datacenter & Communications 业务强 | 光互联是真受益链条 |
| Fabrinet | Q3 FY2026 revenue 12.14 亿美元，同比高增 | 光通信制造受益，但要看利润捕获 |
| Delta Electronics | Q1 2026 净利同比大增，AI 数据中心电源/热管理需求驱动 | 是 AI power/thermal 的核心观察标的 |
| TSMC | Q1 2026 revenue 约 359 亿美元，AI/HPC 和先进封装需求强 | AI 芯片制造底座仍紧 |

## 6. 真正的死角

1. 订单不是利润：服务器、ODM、制造服务最容易踩这个坑。
2. FCF 比 EPS 更重要：扩产周期中，会计利润可能好看，现金流被 capex 吃掉。
3. 存货是早期预警：AI 供应链一旦补库存过头，存货和应收会先恶化。
4. 技术路线会改利润池：HBM4、CPO、硅光、铜互联、NVLink Fusion、ASIC 都可能重分蛋糕。
5. 大客户不是永远友好：NVIDIA、云厂商都有能力压价、扶持二供、调整架构。
6. 涨幅越大，容错越低：过去一年涨 5-10 倍的标的，未来必须持续超预期。
7. 第二层客户可能是“花钱方”：云厂商的 capex 是 NVIDIA 的收入，但不自动等于云厂商利润。

## 7. 术前纪律

任何标的进入交易层前，必须回答这 10 个问题：

1. AI 相关收入占比是多少？
2. 毛利率是上行、持平还是被大客户压价？
3. backlog 有没有？取消条款和价格条款是否清楚？
4. 存货和应收有没有异常上升？
5. capex 是否大幅上升？未来会不会产能过剩？
6. 经营现金流是否跟上净利润？
7. 客户集中度是否过高？
8. 过去一年涨幅是否已经透支 2-3 年增长？
9. 技术路线替代会不会削弱它的环节？
10. 如果 NVIDIA 或云厂商砍单 20%，这家公司利润会掉多少？

## 8. 当前最合理的研究顺序

1. 硬底座：TSMC、SK Hynix、Broadcom。
2. 高弹性瓶颈：Marvell、Coherent、Lumentum、Vertiv、Delta。
3. 利润穿透验证：Dell、HPE、Fabrinet、鸿海、广达、纬颖。
4. 第二层客户验证：Microsoft、Alphabet、Amazon、Meta、Oracle、CoreWeave/Nebius。

## 9. 一句话总结

NVIDIA 链确实像 AI 时代的果链，但不是所有链上公司都值得买。真正值得跟的是“硬瓶颈 + 有议价权 + 有现金流穿透”的公司；最危险的是“只沾订单、利润薄、股价已经按瓶颈估值”的公司。
