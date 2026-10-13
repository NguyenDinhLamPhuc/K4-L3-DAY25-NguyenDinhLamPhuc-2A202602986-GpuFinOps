# NimbusAI FinOps: từ đo lường đến hành động

## Baseline và optimized

Theo báo cáo M5 hiện tại, chi phí baseline ước tính là $27,133/tháng, còn optimized là $14,626/tháng. Mức giảm $12,507/tháng, tương đương 46%. Riêng traffic inference trong M2 giảm từ $48.87 xuống $8.48/ngày. Chi phí đơn vị giảm từ $6.488 xuống $1.126 trên một triệu token (giảm khoảng 82.6%). M2 mô phỏng cascade sang model nhỏ, cache và batch; đây là kết quả theo giá và workload mẫu của lab, không phải hóa đơn thực tế.

Các số tổng hợp phản ánh các đòn bẩy trong M1–M3/M5 và có thể chịu ảnh hưởng của giả định trong mô hình. Đặc biệt, extension cache đã bổ sung hàm break-even `cache_is_worth_it()`.

## Đòn bẩy và GPU-Util Lie

Đòn bẩy lớn nhất trong báo cáo M5 là purchasing (spot/reserved): $10,040/tháng, chiếm phần lớn tổng savings. M3 chọn spot cho job interruptible và reserved cho workload có duty cycle cao; mức break-even với discount reserved 45% là 55% utilization. M2 inference đóng góp $1,212/tháng trong breakdown M5; hai khoản tiếp theo là tắt GPU idle ($600/tháng) và right-size util-lie ($655/tháng).

M1 đánh dấu **`gpu-h100-4`** (GPU-Util 98.2%, MFU 0.194) và **`gpu-a10g-1`** (96.9%, MFU 0.268) là GPU-Util Lie: phần trăm hoạt động cao nhưng tỷ lệ FLOPs hữu ích thấp. Theo telemetry một ngày, **`gpu-h100-5` có 8 giờ idle**, tương đương $20/ngày hay $600/tháng nếu tiếp tục chạy ở on-demand. Báo cáo M5 ước tính right-sizing các util-lie tiết kiệm thêm $655/tháng.

## Các phần mở rộng đã làm

**Extension 2 — right-sizing theo MBU:** M1 tính MBU, `$ / GB-VRAM-hour` và so sánh dung lượng VRAM cùng peak bandwidth. Sáu GPU H100 trong telemetry được gợi ý chuyển sang MI300X: cùng 80 GB VRAM, peak bandwidth 5.30 TB/s so với 3.35 TB/s của H100, và chi phí catalog trên GB-VRAM-giờ giảm từ **$0.0312 xuống $0.0102**. Đây là ứng viên để benchmark cho inference memory-bound, không phải khẳng định hiệu năng ứng dụng tương đương; MBU hiện tại của workload được dùng làm target.

**Extension 3 — cache break-even:** `cache_is_worth_it()` trả về true khi tổng savings từ các lần đọc vượt chi phí ghi; mặc định cache read trả 10% giá thông thường nên mỗi lần đọc tiết kiệm 90%. Hai đầu vào phải cùng đơn vị chi phí trên một triệu token. Extension hiện có logic tính quyết định nhưng chưa nối vào lựa chọn cache của M2.

**Extension 4 — reasoning budget:** M2/M5 tách `is_reasoning=1` khỏi traffic thường và so sánh cùng **1,241,156 token**. Trên lượng token bằng nhau, energy model cho reasoning dùng **80× Wh**. Chi phí được chuẩn hóa theo standard route, áp dụng cùng giả định model/cache/batch theo từng cohort; mẫu này cho reasoning bằng **0.86× chi phí**, vì vậy dữ liệu chưa chỉ ra phụ phí đô-la từ reasoning độc lập với model routing. Đề xuất routing là chỉ bật reasoning khi confidence dưới **0.70**, rồi hiệu chỉnh ngưỡng bằng chất lượng và latency. Dataset không có confidence score, nên ngưỡng này là chính sách khởi đầu, chưa phải kết quả tối ưu hóa được kiểm chứng.

## Ba hành động đầu tiên cho NimbusAI

1. **Tắt hoặc autosuspend GPU idle**, bắt đầu với `gpu-h100-5`; đặt cảnh báo idle và yêu cầu chủ workload xác nhận trước khi giữ instance chạy qua đêm.
2. **Benchmark hai GPU-Util Lie và ứng viên MI300X** trên workload đại diện, đo throughput, latency, chất lượng và chi phí/token; sau đó chỉ chuyển workload đạt cùng yêu cầu VRAM/bandwidth.
3. **Triển khai routing có guardrail:** dùng spot cho job thực sự interruptible có checkpoint, kiểm tra utilization trước commitment reserved; thử ngưỡng confidence 0.70 cho reasoning theo canary và theo dõi chất lượng, latency, Wh/token trước khi rollout.


