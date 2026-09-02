---
title: 稳定性与控制 (Stability & Control)
---

# 稳定性与控制

## n=0 垂直不稳定性

无质量刚性位移模：外场刚度 $k=I_p\,\partial^2\psi_{\rm ext}/\partial Z^2$
（$k>0$ 失稳），被动结构经耦合梯度 $G_k=\partial M_{pk}/\partial Z_p$ 响应，
增长率解色散关系

$$k = \gamma\,I_p^2\,G^\mathsf{T}(\gamma M + R)^{-1}G$$

三档判读由模型自身给出：`stable` / `resistive-wall` / `ideal-unstable`。

```python
v = S.vertical_mode(g, tables, coil_aturns=..., device=dev,
                               passive_groups=("inner_shell","outer_shell","passive_plates"))
print(v.regime, v.growth_rate, v.stiffness, v.margin)
```

### 铜板值两个量级

| 被动集 | γ [1/s] | margin |
| :--- | ---: | ---: |
| 仅内壳 | 3437 | 0.068 |
| 内 + 外壳 | 2330 | 0.071 |
| 内壳 + **铜板** | 13.7 | 0.684 |
| **全 90 段** | **12.6** | **0.686** |

最靠近等离子体的 10 块铜板正是为压 γ 而装。**只用内壳会把 γ 高估 270 倍**。

### 两条极限判据

- $\eta \times 2 \Rightarrow \gamma \times 2$ **恰好**（色散关系的标度不变性，
  比单调性更强）；
- 壁靠近 $\Rightarrow \gamma$ 降：`vessel_scale` 0.80→1.15 上 γ 由 3.19 单调升至 141.7。

### 逐步 GS 假定的适用边界

给刚性模加回等离子体惯性（色散多一项 $m\gamma^2$）：实测 $m=9.1\times10^{-7}$ kg、
$\sqrt{k/m}=5.5\times10^5$ rad/s 而 $\gamma=12.6$ s⁻¹，**惯性修正仅 $2\times10^{-9}$**。
故逐步 GS 假定在此位形上精确到 9 位有效数字，失效要等到微秒级增长（破裂领域）。

## 垂直反馈回路

等离子体经无质量力平衡消元，折成导体互感的**秩一修正**
$M^*=M-I_p^2GG^\mathsf{T}/k$——**小信号域里等离子体确实反作用于电路**。

```python
sysv = K.vertical_system(g, tables, ic_coils=dev["ic_coil"]["coils"], ...)
r = K.close_vertical_loop(sysv, t_end=1.0, dt=2e-4, kp=300., kd=0.3,
                          use_observer=True, noise_rms=0.02, v_max=100.)
```

判据是**断环必须发散、闭环必须归零**：断环 ξ 1 mm → 5.4e7 mm；
闭环 kp=300/kd=0.3 无过冲回到设定值 <1%，IC 上仅 0.3 V/turn；
**磁通环观测器 + 2% 噪声 + 100 V 限幅仍收敛**。

`eig(-M^{*-1}R)` 的 γ 精确满足上面的色散关系（Sherman–Morrison，残差 <1e-8）——
两条独立编码路径互证。

## 形状响应矩阵

:::{important}
**本节与下一节的两个入口都经 `fylite.run.forward_equilibrium` 取那两次 GS 解，而它在
本分发里是录得参考的读取器。** `libefit.so` 与 Green 表按 LICENSE 3.1 移除，录得的答案
留下了：`shape.shape_response` 与 `pulse.design_trajectory` 对**录过的**输入照旧算得出来
（`tests/data/oracle/efit.forward_equilibrium/` 297 条；`tests/test_shape.py` 即跑在这条路
上），对没录过的抛 `OracleMissing`——一列中心差分要的是**两次新的** GS 解，所以在新位形上
这两个入口今天走不通。下面的数字是当年实测，结论仍成立：差分真求解器与解析摄动的差别不随
求解器换人而变。原委见 [Fortran 制品去哪了](#fortran-artifacts)。
:::

TokSys 走解析摄动 GS（`gspert`）；fylite **直接差分真求解器**——一次正解 0.05 s，
一列中心差分就是两次诚实的 GS 解，响应因而属于下游实际使用的那个算子。

```python
tg = SH.ShapeTargets(gaps=(...), isoflux=(...), angles=(0., 90., 270.))
resp = SH.shape_response(meas, aturns, tg)
pred = SH.predict_shape_change(resp, delta_aturns)
```

线性度实测：控制级观测量（gap/isoflux/轴/角采样边界点）对有限扰动的预测误差
**0.1–0.5%**，且对差分步长 1%→50% 稳定（非量化伪象）。

:::{tip}
角采样边界点由**射线与 ψ 场求交**得到，不是插值 g-file 的边界折线——
后者是为绘图采样的，插值它会带来 10–25% 的响应误差。
:::

## 前馈轨迹设计（GSPulse 型）

给定目标形状**序列**求电压波形，整条脉冲一次求解：外层全时程二次代价 ↔
逐轮重线性化。QP 以**纯 numpy 带界最小二乘**求解（唯一约束是导体动力学这条
线性等式，代入消元即无约束问题），故不引入 QP 包。

```python
d = PU.design_trajectory(meas, time, targets, obs_ref, x0,
                         device=..., limits=True)
d["feasible"], d["residual_m"], d["channels_over_voltage"]
```

**电源额定是硬约束**。后果很实在：3 cm gap 斜坡在 50 ms 内**在 EAST 上不可行**——
不加约束的设计会让 12 个通道里 7 个越压（最劣 8.5×）。电源电压限制的是形状变化的
**速率**：同样 3 cm 给到 300 ms 即可行，0.5 cm 在 50 ms 内可行。

电流限值的检查会**自证其错**：初始状态是真实炮的电流，若某通道的导出限值连它都
违反，那是**限值错而非设计错**——此类通道报为 `channels_current_limit_suspect`
并排除出违规名单。

## 击穿与上升段

等离子体存在**之前**的那一段：目标不是形状，而是可雪崩的**极向场零点**与足够的
**磁通预算**。纯真空、无 GS 解、场对电流线性，故整个设计是一次小最小二乘。

```python
from fylite.scenario import design as B
d = B.breakdown(r0=1.85, z0=0.0, radius=0.3, flux_target=0.3, device=dev)
d["feasible"], d["b_max"], d["null_ok"], d["flux_Wb"], d["flux_error"]
```

★入口名与形参都变过：它曾是 `fylite.breakdown.design_null(tables, dev, …)`，现在是
`fylite.scenario.design.breakdown(...)`，**全关键字**、不收位置参数，返回的也是一层平表
（`d["b_max"]`，不再是 `d["null"]["b_max"]`）。同名的 `kernel.design_null` 是它底下那一层
纯数值的最小二乘，收的是场与磁通的**行**而不是装置。

实测（装置取 `$FYLITE_DEVICE_DIR/east_device.yaml`，1336 次迭代）：0.3 m 盘内
**|B| 峰 7.15e-6 T**（rms 2.7e-6、中心 1.4e-7），磁通 **0.2794 Wb / 目标 0.3**，
`feasible` 为真——两条判据都过。开关 `limits` 同解，说明这个设计远在电源额定之内。

★旧文档在这里记的是「|B| 峰 0.0077 mT、磁通命中到 2.2e-4」。前一个数与上面一致
（0.0077 mT = 7.7e-6 T），后一个不是：那是 EFIT 表目录还在、由它作首个位置参数时的
调用；今天按装置文档重测就是上面这组。

:::{warning}
**量纲必须显式归一**。零点行是特斯拉（~1e-3）、磁通行是韦伯（~1e-1）；
不按各自容差归一，磁通会完全压倒零点，"设计"出来的是 14 mT 的**均匀场而非零点**
——`max ≈ rms ≈ 中心` 正是它的征兆。
:::

## 跨码对标

整条链已与 GA 的 TokSys `rzrig` 逐量交叉验证：

| 量 | fylite | TokSys | 差 |
| :--- | ---: | ---: | ---: |
| 质心 $B_z$ | −0.0662 T | −0.0660 T | 0.3% |
| 刚度 $k$ | 280 232 N/m | 278 916 N/m | 0.47% |
| 稳定裕度 | 0.6856 | 0.6906 | 0.72% |
| $\gamma_z$（同导体集） | 9.177 s⁻¹ | 9.458 s⁻¹ | 2.97% |

:::{important}
$\gamma$ **必须在同一导体集上比**。rzrig 把主动线圈放进电路，故可比对象是
`control.vertical_system`，而非仅被动的色散（后者给 12.64 s⁻¹，是刻意更悲观的
问法）。两者都对，但不可混比。
:::

★走查用的 notebook 已不在本仓，仓根 `examples/` 也已删除——今天的可跑示例是算例语料（`cases/`），见[算例语料](cases.md)起的五章。