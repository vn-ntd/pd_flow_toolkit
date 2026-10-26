# Physical Design (PD) Flow Automation Toolkit

> **Công cụ phụ trợ tự động hóa trong quy trình ASIC/SoC Physical Design**
> Giải quyết bài toán lặp đi lặp lại: Parse báo cáo Signoff (WNS, TNS, DRC, Congestion), sinh Dashboard HTML trực quan và Lint kiểm tra tính toàn vẹn của file SDC trước khi chạy Synthesis / P&R.

---

## 🎯 Giới thiệu Dự án (Overview)

Trong quy trình thiết kế vi mạch VLSI/ASIC Physical Design (PD), kỹ sư thường xuyên phải thực hiện các tác vụ tốn thời gian và dễ nhầm lẫn:
1. **Kiểm tra tính toàn vẹn của ràng buộc thời gian (SDC)** trước khi chạy Synthesis và P&R: Lỗi clock, unconstrained ports, wildcard false paths làm sai lệch kết quả tối ưu.
2. **Thu thập, đọc thủ công hàng chục file báo cáo (`.rpt`, `.summary`, `.drc`, `.log`)** sau mỗi vòng lặp P&R (OpenROAD hoặc Cadence Innovus) để kiểm tra Timing Slack (WNS/TNS), DRC violations, Congestion hotspots, Area và Power.
3. **So sánh regression giữa các lần chạy (Run A vs Run B)** sau các bước ECO để đánh giá cải thiện hay suy giảm (timing/DRC regression).

**PD Flow Toolkit** cung cấp một giải pháp tự động hóa toàn diện, hiệu năng cao, viết bằng Python 3 chuẩn (sử dụng thư viện tiêu chuẩn của Python kết hợp thư viện gọn nhẹ `rich` để render CLI terminal trực quan, không phụ thuộc framework web cồng kềnh, hoàn toàn tương thích môi trường server EDA nội bộ).

---

## 🚀 Các tính năng chính (Key Features)

### 1. 📊 PD Report Parser & Interactive HTML Dashboard
- Hỗ trợ cả **OpenROAD / OpenSTA** (Open-source EDA) và **Cadence Innovus** (Commercial EDA).
- Trích xuất tự động:
  - **Timing Setup & Hold**: WNS (Worst Negative Slack), TNS, Failing Endpoints (FEP), Clock Skew, Max Transition/Capacitance violations.
  - **DRC Violations**: Tổng số lỗi DRC, phân loại theo rule (`Short`, `MinSpacing`, `MinArea`, `ViaSpacing`), thống kê theo layer kim loại (`Metal1`, `Metal2`, `Metal3`, `Via1`).
  - **Routing Congestion**: Horizontal & Vertical max congestion (%), Overflows count, Hotspots.
  - **Area & Power**: Die/Core area, Core utilization %, Standard cell count, Macro count, Dynamic & Leakage power.
- Xuất dữ liệu:
  - Terminal summary table có màu trực quan.
  - Định dạng chuẩn **JSON** phục vụ CI/CD regression pipeline.
  - **Standalone Interactive HTML Dashboard**: Thiết kế Dark mode hiện đại, KPI cards, biểu đồ thanh trực quan cho metal layer violations, chạy hoàn toàn offline không cần internet.

### 2. 🛡️ SDC Integrity Checker & Linter
Phân tích file Synopsys Design Constraints (`.sdc`) trước khi đưa vào Design Compiler / Yosys / Innovus:
- **`CLK-001`**: Kiểm tra định nghĩa primary clocks và chu kỳ `period > 0`.
- **`CLK-002`**: Kiểm tra tính hợp lệ của waveform (rising edge < falling edge <= period).
- **`CLK-003`**: Kiểm tra `create_generated_clock` có đủ `-source`, `-master_clock` hợp lệ, quan hệ chia tần/nhân tần.
- **`CLK-004`**: Phát hiện định nghĩa trùng tên clock (`duplicate clock name`).
- **`CLK-005`**: Kiểm tra `set_clock_uncertainty` (Jitter & Margin) cho từng clock domain.
- **`CLK-006`**: Kiểm tra `set_clock_transition` cho ideal clock network trước CTS.
- **`IO-001 / IO-002`**: Phát hiện I/O ports bị unconstrained (thiếu `set_input_delay` / `set_output_delay`).
- **`IO-003`**: Cảnh báo I/O delay bất thường (> 85% clock period hoặc negative delay).
- **`EXC-001`**: Bắt các timing exceptions nguy hiểm dùng wildcard broad mask (`set_false_path -from * -to *`) dễ che giấu critical timing paths.
- **`EXC-002`**: Phát hiện xung đột giữa False Path và Multicycle Path trên cùng pin/register.
- **`EXC-003`**: Kiểm tra cú pháp Multicycle setup/hold.
- **`CDC-001`**: Cảnh báo thiếu `set_clock_groups -asynchronous` khi thiết kế có nhiều clock độc lập.
- **`SYN-001`**: Cảnh báo lệnh SDC lỗi thời hoặc không tương thích flow synthesis hiện đại.

### 3. ⚖️ Run Regression Comparator (Diff Engine)
- So sánh 2 lần chạy PD (Baseline vs Current / Run 1 vs Run 2).
- Tự động tính toán Delta: $\Delta$WNS, $\Delta$TNS, $\Delta$DRC, $\Delta$Congestion, $\Delta$Utilization.
- Đánh dấu màu Xanh (cải thiện) và Đỏ (suy giảm/regression) giúp kỹ sư PD ra quyết định ký duyệt ECO.

---

## 📁 Cấu trúc Thư mục Dự án

```
pd_toolkit/
├── pd_tool.py                      # CLI Entry point chính
├── README.md                       # Tài liệu hướng dẫn sử dụng chi tiết
├── requirements.txt                # Yêu cầu môi trường (chuẩn Python 3.10+)
├── pd_toolkit/                     # Source code module chính
│   ├── __init__.py
│   ├── cli.py                      # Giao diện dòng lệnh CLI (Argparse + Rich styling)
│   ├── parsers/                    # Engine phân tích báo cáo EDA
│   │   ├── __init__.py             # Auto-detect OpenROAD / Innovus
│   │   ├── base_parser.py          # Data models: PDRunMetrics, Timing, DRC, Congestion
│   │   ├── openroad_parser.py      # Parser cho OpenROAD / OpenSTA / TritonRoute
│   │   └── innovus_parser.py       # Parser cho Cadence Innovus / timeDesign / verifyGeometry
│   ├── dashboard/                  # Generator Dashboard HTML
│   │   ├── __init__.py
│   │   └── generator.py            # Sinh standalone HTML5 dashboard
│   ├── sdc_linter/                 # Bộ kiểm tra ràng buộc SDC
│   │   ├── __init__.py
│   │   ├── sdc_parser.py           # SDC tokenizer, handle continuation (\), quotes, brackets
│   │   ├── rules.py                # Định nghĩa hệ thống rule checks & gợi ý sửa
│   │   └── linter.py               # Linter runner & xuất báo cáo
│   └── comparator/                 # Engine so sánh regression
│       ├── __init__.py
│       └── diff_engine.py          # Tính delta & đánh giá xu hướng chất lượng P&R
├── examples/                       # Dữ liệu mẫu & kết quả thực tế
│   ├── picorv32_dashboard.html     # Real dashboard trích xuất từ repo RISC-V PicoRV32 (SkyWater 130nm)
│   ├── openroad_run/               # Mock reports OpenROAD (timing, DRC, congestion, area)
│   ├── innovus_run/                # Mock reports Cadence Innovus
│   └── sdc/
│       ├── clean_soc.sdc           # File SDC chuẩn không lỗi (Golden template)
│       └── dirty_soc.sdc           # File SDC mẫu chứa các lỗi thiết kế phổ biến
└── tests/                          # Automated Unit Test Suite
    ├── test_parsers.py
    ├── test_sdc_linter.py
    └── test_comparator.py
```

---

## ⚡ Hướng dẫn Sử dụng (Quick Start)

### 1. Chạy Demo trọn gói kiểm tra toàn bộ tính năng
```bash
python pd_tool.py demo
```

### 2. Parse báo cáo PD và sinh HTML Dashboard
```bash
# Đối với OpenROAD flow:
python pd_tool.py parse --path examples/openroad_run --tool openroad --design riscv_core --dashboard openroad_dash.html

# Đối với Cadence Innovus flow:
python pd_tool.py parse --path examples/innovus_run --tool innovus --design gpu_tile --dashboard innovus_dash.html

# Tự động nhận diện flow và xuất JSON / Markdown cho CI/CD (GitHub Actions / GitLab CI):
python pd_tool.py parse --path /path/to/pd/run --output-json metrics.json --output-md summary.md --dashboard signoff.html
```

### 3. Kiểm tra tính toàn vẹn file SDC (Pre-Synthesis Linting)
```bash
# Kiểm tra file SDC chuẩn:
python pd_tool.py lint-sdc --sdc examples/sdc/clean_soc.sdc

# Kiểm tra file SDC có lỗi và xuất JSON / Markdown:
python pd_tool.py lint-sdc --sdc examples/sdc/dirty_soc.sdc --output-json sdc_lint_report.json --output-md sdc_report.md

# Bật cờ fail khi có cảnh báo (dành cho CI/CD regression):
python pd_tool.py lint-sdc --sdc constraints.sdc --fail-on-warning
```

### 4. So sánh Regression giữa 2 lần chạy P&R (Đầy đủ tam giác PPA: Power - Timing - Area)
```bash
# So sánh và in bảng terminal trực quan:
python pd_tool.py compare --baseline examples/openroad_run --current examples/innovus_run

# So sánh và xuất báo cáo Markdown / JSON cho CI/CD PR comment:
python pd_tool.py compare --baseline examples/openroad_run --current examples/innovus_run --output-md regression_diff.md --output-json regression_diff.json
```

### 5. Chạy Automated Unit Tests & Kiểm Tra Độ Bao Phủ Mã Nguồn (Coverage)
```bash
# Chạy với unittest chuẩn:
python -m unittest discover -s tests -p "test_*.py"

# Chạy với pytest và xuất bảng thống kê độ bao phủ (Coverage >= 85%):
pytest --cov=pd_toolkit --cov-report=term-missing

# Kiểm tra cú pháp và chất lượng mã nguồn (Linting):
ruff check .
flake8 pd_toolkit tests --max-line-length=120 --extend-ignore=E501,W503
```

---

## 📊 Kết quả Mẫu HTML Dashboard
Dashboard sinh ra dưới dạng file HTML độc lập (`dashboard.html`), có thể mở trực tiếp trên mọi trình duyệt (Chrome, Firefox, Edge) hoặc nhúng vào Jenkins/GitLab CI artifact:
- **KPI Badges**: Hiển thị trạng thái Signoff tổng thể (`PASS`, `WARN`, `FAIL`).
- **Slack Metrics**: Bảng chi tiết WNS/TNS/FEP, Slew/Capacitance violations.
- **DRC & Metal Layers**: Biểu đồ phân bổ vi phạm theo lớp kim loại (Metal1, Metal2, Via1,...).
- **Congestion Bar**: Thước đo trực quan mức độ nghẽn đường dây (H-Max / V-Max).
