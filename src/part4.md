# 第 5 章 应用技术案例题精讲与配置模板

应用技术 4 道大题，真正拉开差距的是第 2 题（配置）和第 4 题（排障）。这两类题的答案高度模板化，**背熟模板比刷题更有效**。

## 5.1 案例题四步答题框架

| 步骤 | 动作 | 时间 | 产出 |
|---|---|---|---|
| 读需求 | 圈出“隔离/冗余/带宽/成本/运维简单”等关键词 | 3 分钟 | 需求清单 |
| 定结构 | 判断层次（核心/汇聚/接入）、确定 VLAN 与地址规划 | 5 分钟 | 拓扑草图 + 地址表 |
| 写配置 | 按“接口 → VLAN → 路由 → 策略 → 服务”顺序补全 | 20 分钟 | 命令行填空 |
| 验结果 | 用 ping/tracert/display 命令验证，回填结论 | 5 分钟 | 验证命令 + 预期输出 |

**得分点意识**：阅卷按“关键命令 + 关键参数”给分。哪怕整段配不出来，把 §port link-type trunk§、§port trunk allow-pass vlan 10 20§ 这类骨架写对，也能拿到大部分分。**不要留空**，宁可写思路。

## 5.2 交换配置模板

### 5.2.1 VLAN 与 Trunk

~~~bash
vlan batch 10 20 100                    # 批量创建 VLAN
interface GigabitEthernet0/0/1
 port link-type access                  # 接终端
 port default vlan 10                   # PVID = 10
interface GigabitEthernet0/0/24
 port link-type trunk                   # 上联口
 port trunk allow-pass vlan 10 20 100   # 允许通过的 VLAN
 port trunk pvid vlan 1                 # Native VLAN（默认 1）
~~~

### 5.2.2 链路聚合

~~~bash
interface Eth-Trunk 1
 mode lacp-static                       # LACP 模式，推荐
 port link-type trunk
 port trunk allow-pass vlan all
interface GigabitEthernet0/0/23
 eth-trunk 1
interface GigabitEthernet0/0/24
 eth-trunk 1
~~~

要点：成员口的速率、双工、VLAN 配置必须一致；LACP 模式下两端都要配置。

### 5.2.3 生成树

~~~bash
stp mode rstp                           # 或 mstp
stp instance 0 root primary             # 指定本机为根桥
stp priority 4096                       # 或手工调优先级（步长 4096）
interface GigabitEthernet0/0/1
 stp edged-port enable                  # 接终端的边缘端口，跳过监听学习
stp bpdu-protection                     # 全局 BPDU 保护，防私接交换机
~~~

### 5.2.4 端口安全

~~~bash
interface GigabitEthernet0/0/5
 port-security enable
 port-security max-mac-num 1            # 最多学习 1 个 MAC
 port-security protect-action restrict  # 超限丢弃并告警
~~~

## 5.3 路由与网关模板

### 5.3.1 静态路由与默认路由

~~~bash
ip route-static 192.168.20.0 255.255.255.0 10.1.1.2
ip route-static 0.0.0.0 0.0.0.0 200.1.1.1  # 默认路由
ip route-static 192.168.30.0 24 10.1.1.3 preference 100  # 浮动静态（备份）
~~~

### 5.3.2 OSPF

~~~bash
ospf 1 router-id 1.1.1.1
 area 0.0.0.0
  network 10.1.1.0 0.0.0.255            # 反掩码！
  network 192.168.10.0 0.0.0.255
#
interface GigabitEthernet0/0/1
 ospf enable 1 area 0.0.0.0             # 接口视图宣告，二选一
~~~

### 5.3.3 NAT（出口访问互联网）

~~~bash
acl 2000
 rule 5 permit source 192.168.0.0 0.0.255.255
interface GigabitEthernet0/0/0
 nat outbound 2000                      # NAPT，多对一
#
interface GigabitEthernet0/0/0
 nat server protocol tcp global 200.1.1.10 80 inside 192.168.10.100 80
~~~

### 5.3.4 ACL（访问控制）

~~~bash
acl 3000
 rule 5 permit tcp source 192.168.10.0 0.0.0.255 destination 192.168.20.0 0.0.0.255 destination-port eq 80
 rule 10 deny ip source 192.168.10.0 0.0.0.255 destination 192.168.20.0 0.0.0.255
 rule 20 permit ip
interface GigabitEthernet0/0/2
 traffic-filter inbound acl 3000
~~~

注意 ACL 的**匹配顺序**：从小到大，命中即停。所以“先 permit 具体、再 deny 范围、最后 permit any”是标准写法。

### 5.3.5 VRRP（网关冗余）

~~~bash
interface Vlanif 10
 ip address 192.168.10.2 255.255.255.0
 vrrp vrid 10 virtual-ip 192.168.10.1   # 虚拟网关
 vrrp vrid 10 priority 120              # 默认 100，大者为 Master
 vrrp vrid 10 preempt-mode timer delay 20
~~~

备机配置相同 vrid 与 virtual-ip，优先级保持默认 100，不配 priority 即为备。

## 5.4 服务与安全模板

### 5.4.1 DHCP

~~~bash
dhcp enable
ip pool vlan10
 gateway-list 192.168.10.1
 network 192.168.10.0 mask 255.255.255.0
 dns-list 114.114.114.114
 excluded-ip-address 192.168.10.200 192.168.10.254
 lease day 3
interface Vlanif 10
 dhcp select global
~~~

跨网段时用中继：

~~~bash
interface Vlanif 20
 dhcp select relay
 dhcp relay server-ip 10.1.1.10
~~~

### 5.4.2 无线 AC（瘦 AP 架构）

~~~bash
capwap source interface Vlanif 100      # AC 与 AP 通信的源接口
wlan
 security-profile name sec
  security wpa2 psk pass-phrase Huawei@123 aes
 ssid-profile name office
  ssid office-wifi
 vap-profile name office
  security-profile sec
  ssid-profile office
  service-vlan vlan-id 10
 ap-group name office
  vap-profile office wlan 1 radio all
~~~

### 5.4.3 防火墙策略（华为 USG）

~~~bash
security-zone name trust
 add interface GigabitEthernet1/0/1
security-zone name untrust
 add interface GigabitEthernet1/0/2
security-policy
 rule name allow-web
  source-zone trust
  destination-zone untrust
  service http https
  action permit
 rule name default-deny
  action deny
~~~

## 5.5 故障排查题的答题模板

排障题的标准答案结构是**“现象 → 分层定位 → 依据 → 处置 → 验证”**，五句话拿满分：

1. **现象**：终端无法访问某服务器 / 某网段互通失败 / 无线连不上。
2. **定位**：从物理层往上查，先看接口状态，再看 VLAN/Trunk，再看路由与 ACL。
3. **依据**：引用 show 输出中的关键行（如 §Line protocol current state : DOWN§）。
4. **处置**：给出具体命令与配置修改。
5. **验证**：§ping§、§tracert§、§display ip routing-table§ 的结果。

**示例**：某 VLAN 20 的终端无法获取 IP，其它 VLAN 正常。

| 步骤 | 检查项 | 命令 | 判断 |
|---|---|---|---|
| 1 | 接口是否 up | §display interface GigabitEthernet0/0/8§ | 物理 up、协议 down → 对端问题 |
| 2 | VLAN 是否存在 | §display vlan 20§ | 不存在则 §vlan 20§ |
| 3 | 端口 PVID | §display port vlan§ | PVID 是否 20 |
| 4 | Trunk 是否放行 | §display port vlan§ / 配置 | 未放行则补 §port trunk allow-pass vlan 20§ |
| 5 | 网关与中继 | §display ip pool name vlan20§ | 地址池耗尽或中继地址错 |
| 6 | DHCP 是否使能 | §display dhcp server statistics§ | 无请求 → 二层问题；有请求无响应 → 服务器/中继问题 |

## 5.6 两道模拟案例（含参考答案）

### 案例一：小型企业网改造

**背景**：某公司有办公区（60 人）、财务区（15 人）、服务器区（5 台）。要求：办公与财务逻辑隔离，财务可访问服务器区的财务系统，办公区只能访问服务器的 Web 门户；出口一条 100 M 宽带，需做地址转换；网关需冗余。

**问题 1**：给出 IP 地址规划（写出网段、掩码、可用地址范围、网关）。

**参考答案**：

| 区域 | 网段 | 掩码 | 可用地址 | 网关（VRRP 虚拟） |
|---|---|---|---|---|
| 办公区 | 192.168.10.0/26 | 255.255.255.192 | .1—.62（62 个） | 192.168.10.62 |
| 财务区 | 192.168.20.0/27 | 255.255.255.224 | .1—.30（30 个） | 192.168.20.30 |
| 服务器区 | 192.168.30.0/29 | 255.255.255.248 | .1—.6（6 个） | 192.168.30.6 |

说明：按“主机数向上取 2 的幂再加 2（网络地址 + 广播地址）”选掩码，办公 60 人需 62 个可用地址，故 /26。

**问题 2**：写出实现“财务可访问服务器、办公只能访问 Web 门户”的 ACL 关键配置。

**参考答案**：

~~~bash
acl 3000
 rule 5 permit ip source 192.168.20.0 0.0.0.31 destination 192.168.30.0 0.0.0.7
 rule 10 permit tcp source 192.168.10.0 0.0.0.63 destination 192.168.30.0 0.0.0.7 destination-port eq 80
 rule 20 deny ip source 192.168.10.0 0.0.0.63 destination 192.168.30.0 0.0.0.7
 rule 30 permit ip
~~~

**评分点**：反掩码写对（/26 → 0.0.0.63，/27 → 0.0.0.31，/29 → 0.0.0.7）；permit 在前、deny 在后；末尾放行其他流量。

### 案例二：无线覆盖与排障

**背景**：办公楼部署 20 个 AP，由 AC 统一管理。员工反映会议室频繁掉线，靠近窗户的位置信号强但速率低。

**问题 1**：分析两个现象的可能原因。

**参考答案**：

- 会议室掉线：AP 密度过高导致同频干扰与漫游频繁；或 AP 功率过大使终端“粘”在远端 AP（粘滞）；也可能是 AC 的 CAPWAP 心跳超时。排查：§display ap all§ 看 AP 状态，§display station all§ 看终端 RSSI 与关联 AP，调整功率与信道。
- 靠窗信号强但速率低：收到室外/邻楼 AP 的同频信号，信噪比低；或该区域 AP 工作在 2.4 GHz 且信道重叠。处置：改用 5 GHz、规划 1/6/11 非重叠信道、开启频段引导（Band Steering）。

**问题 2**：写出关闭 2.4 GHz 射频、只保留 5 GHz 的关键命令思路。

**参考答案**：在 AP 组或射频视图下关闭 2.4 GHz 射频（§radio 0 shutdown§ 或通过射频调优模板限制频段），并确认业务 VAP 绑定到 5 GHz 射频。具体命令随 AC 型号与版本略有差异，答题时写出“在 AP 组射频视图关闭 radio 0”即可得分。

# 第 6 章 备考路线与考前 6 天冲刺

## 6.1 三阶段路线（适用于还有 2—3 个月的人）

| 阶段 | 时长 | 核心动作 | 检验标准 |
|---|---|---|---|
| 打地基 | 3—4 周 | 通读教材 + 第 3 章，每个知识域画一张思维导图 | 能口述 OSI 各层协议、TCP 三次握手、OSPF 邻居状态 |
| 刷题强化 | 3—4 周 | 按知识域刷真题，错题归因（概念/计算/读题） | 基础知识稳定 55 分以上，错题本不超过 30 条 |
| 冲刺 | 2 周 | 全真限时套卷 + 案例模板默写 | 240 分钟连考能完整答完两科 |

**每天的时间配比建议**：40% 做题、30% 看错题与教材、20% 背模板与表格、10% 英语。

## 6.2 考前 6 天冲刺表（2026 年 10 月 18—24 日）

| 日期 | 上午（2 h） | 下午（2 h） | 晚上（1 h） |
|---|---|---|---|
| 10/18 周日 | 第 4 章 27 题限时 60 分钟做完，对答案 | 错题回第 3 章补漏（只补错的那几个小节） | 背附录 A 端口表 + 附录 B 默认值 |
| 10/19 周一 | 机考模拟平台熟悉界面（标记、跳转、交卷） | 第 5 章配置模板，遮住解释逐行口述 | 背 OSPF/RIP/BGP 对比表 |
| 10/20 周二 | 全真模拟：基础知识 75 题限时 105 分钟 | 应用技术 4 大题限时 135 分钟 | 复盘：算分，找失分最多的题型 |
| 10/21 周三 | 专攻计算题（子网、信道容量、时延）20 题 | 专攻配置题（VLAN/OSPF/NAT/ACL/VRRP）各写一遍 | 背网络安全法四要素 + 等级保护 |
| 10/22 周四 | 第二次全真模拟（240 分钟连考，不暂停） | 同上（连续做） | 只看错题本，不做新题 |
| 10/23 周五 | 过一遍附录 C 命令速查 + 第 2.4 节陷阱清单 | 熟悉考场路线、检查证件与准考证 | 早睡，不再刷题 |
| 10/24 周六 | 考前 2 小时只看两张表（端口表、协议对比表） | 14:30—18:30 考试 | — |

> 如果你现在才开始准备，这张表仍然可用——把“全真模拟”减为一次，其余时间全部用来背模板和第 4 章错题。考前 6 天能提的分，主要来自“少丢分”而不是“多学新知识”。

## 6.3 240 分钟怎么分配

| 时段 | 科目 | 时长 | 动作 |
|---|---|---|---|
| 0—65 min | 基础知识 | 65 min | 会做的直接选，犹豫超过 60 秒的标记跳过 |
| 65—90 min | 基础知识 | 25 min | 集中处理标记题，用排除法 |
| 90—105 min | 基础知识 | 15 min | 检查漏答、题号错位，确认交卷 |
| 105—115 min | 应用技术 | 10 min | 通览 4 道大题，确定作答顺序 |
| 115—220 min | 应用技术 | 105 min | 先做把握大的，每题控制在 25—35 分钟 |
| 220—240 min | 应用技术 | 20 min | 补全空白、检查命令拼写与单位 |

**两条硬规则**：第一科不要超过 120 分钟（系统上限），否则第二科时间被吞；第二科**不要留空题**，写思路也有分。

## 6.4 答题技巧

**选择题**

- 排除法优先：四个选项先砍掉两个明显错的，正确率立刻从 25% 升到 50%。
- 量纲法：计算结果先看单位，量纲不对的选项直接排除。
- 极值法：问“最大/最小/最高”，先想极端情况（全 0、全 1、满带宽）。
- 绝对化必错：出现“彻底”“完全”“必须”“永远”的选项，除非是定义，否则基本是错的。

**案例题**

- 先写结论再写理由：阅卷老师按点给分，结论写在最前面。
- 命令写不全就写思路：“通过 ACL 限制 192.168.10.0/26 访问 192.168.30.0/29 的 80 端口”也能拿分。
- 数字要带单位：62 个可用地址、100 m、2 ms，缺单位可能被扣分。
- 不要改题干给的地址规划，除非题目明确要求重新规划。

## 6.5 五种典型失败模式

| 失败模式 | 表现 | 对策 |
|---|---|---|
| 只看不练 | 教材翻了 3 遍，没做过一套完整卷 | 每章读完立刻做 10 题 |
| 只刷题不总结 | 做了 2000 题，同类题还错 | 错题按知识域归类，每类只留 3 条 |
| 忽视下午 | 上午 60 分，下午 30 分 | 下午题必须动手写，不能只看答案 |
| 时间失控 | 上午用了 140 分钟 | 平时就按 105 分钟限时训练 |
| 机考不适应 | 找不到标记按钮、输入法打不快 | 考前至少用模拟平台练 2 次 |

# 附录 速查表

## 附录 A 常用端口速查

| 端口 | 协议 | 传输层 | 说明 |
|---|---|---|---|
| 20/21 | FTP | TCP | 数据/控制 |
| 22 | SSH | TCP | 加密远程登录 |
| 23 | Telnet | TCP | 明文远程登录 |
| 25 | SMTP | TCP | 发信 |
| 53 | DNS | UDP/TCP | 查询/区域传送 |
| 67/68 | DHCP | UDP | 服务器/客户端 |
| 69 | TFTP | UDP | 简单文件传输 |
| 80 | HTTP | TCP | Web |
| 110 | POP3 | TCP | 收信 |
| 123 | NTP | UDP | 时间同步 |
| 143 | IMAP | TCP | 收信（同步状态） |
| 161/162 | SNMP | UDP | 轮询/Trap |
| 179 | BGP | TCP | 路由 |
| 443 | HTTPS | TCP | 加密 Web |
| 514 | Syslog | UDP | 日志 |
| 520 | RIP | UDP | 路由 |
| 3389 | RDP | TCP | Windows 远程桌面 |
| 1812/1813 | RADIUS | UDP | 认证/计费 |

## 附录 B 默认值与常用常量

| 项目 | 默认值/常量 |
|---|---|
| STP 桥优先级 | 32768（步长 4096） |
| STP Hello / Forward Delay / Max Age | 2 s / 15 s / 20 s |
| 端口默认 VLAN | 1 |
| Native VLAN | 1 |
| MAC 地址表老化时间 | 300 s |
| VRRP 优先级 / 组播 / 协议号 | 100 / 224.0.0.18 / 112 |
| OSPF Hello / Dead（广播网络） | 10 s / 40 s |
| OSPF 参考带宽 | 100 Mbps（cost = 10⁸/带宽） |
| OSPF 组播 | 224.0.0.5（AllSPF）、224.0.0.6（DR） |
| RIP 更新 / 失效 / 刷新 | 30 s / 180 s / 240 s |
| RIP 最大跳数 | 15（16 为不可达） |
| 以太网最小帧长 | 64 字节 |
| 以太网最大帧长 | 1518 字节 |
| IPv4 首部最小长度 | 20 字节 |
| IPv6 基本首部 | 40 字节 |
| TCP 首部最小长度 | 20 字节 |
| 双绞线最大传输距离 | 100 m |
| 水平布线缆线长度 | ≤90 m |
| 2.4 GHz 非重叠信道 | 1、6、11 |

## 附录 C 华为 VRP 命令速查

| 用途 | 命令 |
|---|---|
| 查看路由表 | §display ip routing-table§ |
| 查看接口简况 | §display ip interface brief§ |
| 查看接口详情 | §display interface GigabitEthernet0/0/1§ |
| 查看 VLAN | §display vlan§ |
| 查看端口 VLAN | §display port vlan§ |
| 查看 MAC 表 | §display mac-address§ |
| 查看 ARP | §display arp§ |
| 查看 STP | §display stp brief§ |
| 查看 OSPF 邻居 | §display ospf peer brief§ |
| 查看 OSPF LSDB | §display ospf lsdb§ |
| 查看当前配置 | §display current-configuration§ |
| 保存配置 | §save§ |
| 清除配置 | §reset saved-configuration§ |
| 重启 | §reboot§ |
| 连通性测试 | §ping 8.8.8.8§ |
| 路径追踪 | §tracert 8.8.8.8§ |
| 查看版本 | §display version§ |
| 查看 CPU/内存 | §display cpu-usage§ / §display memory-usage§ |

## 附录 D 计算公式与单位

| 计算 | 公式 | 备注 |
|---|---|---|
| 奈奎斯特 | C = 2W·log₂N | 理想信道 |
| 香农 | C = W·log₂(1+S/N) | S/N 为功率比；dB → 10^(dB/10) |
| 码元速率 | B = 1/T（波特） | T 为码元周期 |
| 数据速率 | R = B·log₂N | N 为码元种类 |
| 子网数 | 2ⁿ（n 为借位数） | 全 0/全 1 子网是否可用依教材 |
| 可用主机数 | 2ʰ − 2（h 为主机位） | 减去网络地址与广播地址 |
| 块大小 | 256 − 掩码对应字节值 | 快速划分子网 |
| 发送时延 | 数据长度(bit) / 速率(bps) | — |
| 传播时延 | 距离 / 传播速度 | 铜缆约 2×10⁸ m/s，光纤约 3×10⁸ m/s |
| 信道利用率 | 有效数据时间 / 总时间 | — |

## 附录 E 术语中英对照

| 中文 | 英文 | 中文 | 英文 |
|---|---|---|---|
| 带宽 | bandwidth | 吞吐量 | throughput |
| 时延 | latency | 抖动 | jitter |
| 冗余 | redundancy | 收敛 | convergence |
| 封装 | encapsulation | 分片 | fragmentation |
| 组播 | multicast | 广播域 | broadcast domain |
| 子网掩码 | subnet mask | 默认网关 | default gateway |
| 生成树 | spanning tree | 链路聚合 | link aggregation |
| 虚拟局域网 | VLAN | 访问控制列表 | ACL |
| 网络地址转换 | NAT | 虚拟路由器冗余 | VRRP |
| 入侵检测 | IDS | 入侵防御 | IPS |
| 身份认证 | authentication | 加密 | encryption |
| 可扩展性 | scalability | 可用性 | availability |

## 附录 F 参考资料

本文档的制度性信息核对自以下公开文件与页面（访问日期 2026-10-18）：

- 2026 年度计算机技术与软件专业技术资格（水平）考试工作安排（计考办〔2026〕1 号）及山西省工业和信息化厅转发通知：http://gxt.shanxi.gov.cn/xwdt/tzgg/202603/t20260318_10082303.shtml
- 2025 年度上半年考试考务通知（青海省人事考试信息网）：http://qhpta.org.cn/ncms/article_a6e2aa9af68f2e95813c8391c6f88240.shtml
- 2025 年度上半年考试考务通知（山东人事考试信息网）：http://hrss.shandong.gov.cn/rsks/articles/ch03527/202503/704867af-0518-4408-8ae0-2b561bc60a02.shtml
- 2025 年下半年网络工程师考试安排（信管网）：https://m.cnitpm.com/pm1/173623ahdssesry2.html
- 2026 年下半年网络工程师分值占比与时间分配（环球网校）：https://www.hqwx.com/web_news/html/2026-10/17921224885496.html
- 2024 年下半年网络工程师综合知识真题及答案（希赛网）：https://www.educity.cn/rk/5353251.html
- 2025 年下半年网络工程师综合知识真题及答案（CSDN）：https://blog.csdn.net/humor23/article/details/154651872
- 2026 年上半年网络工程师基础知识真题及答案（环球网校）：https://www.hqwx.com/web_news/html/2026-5/17796883962091.html

**免责声明**：真题题干来自考生回忆与机构整理，非官方原卷；答案与解析为编者复核结果，可能存在争议。考试政策以中国计算机技术职业资格网及各省人事考试机构的最新通知为准。
