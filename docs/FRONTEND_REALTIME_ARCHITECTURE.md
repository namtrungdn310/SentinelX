# SentinelX — Frontend Realtime & WebSocket Architecture Guidelines

Tài liệu này đặc tả các nguyên tắc thiết kế, kiến trúc xử lý luồng dữ liệu thời gian thực (Realtime Stream) và giải pháp kỹ thuật phòng ngừa rủi ro cho **Frontend Dashboard (React + TypeScript + Vite)** trong hệ thống SentinelX.

---

## 1. Bối cảnh & Mục đích

Hệ thống SentinelX giám sát hạ tầng máy chủ Linux theo mô hình phân tán nhiều node:
- **Tần suất cao**: Agent đẩy metric CPU/RAM/Disk/Network liên tục (`METRIC_UPDATE`).
- **Bất thường & Đột biến**: Khi có tấn công mạng (SYN Flood, Port Scan) hoặc quá tải tài nguyên, các detector và Incident Correlator bắn ra dồn dập các sự kiện (`DETECTION_ALERT`, `INCIDENT_ALERT`, `INCIDENT_UPDATE`).

Nếu Dashboard xử lý ngây thơ bằng cách `setState` trực tiếp trên từng gói tin WebSocket nhận được, trình duyệt sẽ bị nghẽn CPU, đơ giao diện (UI freeze), sai lệch dữ liệu khi mạng chập chờn và gây quá tải ngược lại cho Controller.

Tài liệu này đặt ra chuẩn mực triển khai bắt buộc cho các kỹ sư frontend.

---

## 2. Các rủi ro kỹ thuật cần loại trừ

| Mã rủi ro | Hiện tượng | Nguyên nhân | Hậu quả |
|---|---|---|---|
| **RISK-01** | Bão tin nhắn (Alert Flooding) | Hàng trăm event đổ về trong vài giây khi có tấn công | React re-render liên tục, tab trình duyệt bị đơ (freeze), tràn RAM |
| **RISK-02** | Lệch trạng thái (State Drift) | Mất kết nối WebSocket tạm thời (vài giây đến vài phút) | Client bỏ lỡ sự kiện trong lúc offline, Dashboard lệch với Database |
| **RISK-03** | Bão kết nối lại (Thundering Herd) | Controller khởi động lại; client thử kết nối lại cùng một thời điểm | Hàng loạt client đồng loạt đập request vào Controller làm sập kết nối |
| **RISK-04** | Tràn bộ nhớ phiên (Memory Leak) | Tab Dashboard mở liên tục nhiều ngày | Các mảng lịch sử telemetry và log sự kiện phình to vô hạn |
| **RISK-05** | Bão thông báo (Alert Fatigue) | Mỗi event bắn 1 toast hoặc phát 1 tiếng chuông | Người vận hành bị ngợp thông tin, giảm khả năng phản ứng chính xác |

---

## 3. Kiến trúc luồng dữ liệu chuẩn (Pipeline Architecture)

Mọi gói tin WebSocket đến từ Controller (`/api/v1/ws`) phải đi qua chuỗi xử lý phân tầng trước khi được đưa vào React State:

```text
WebSocket Frame (/api/v1/ws)
         │
         ▼
[1. Priority Router]
 ├── Pong / Ping ──────────────────────────► Cập nhật Latency (Không render)
 ├── Telemetry Metric (Low Priority) ──────► [2. Throttled Batch Queue (1000ms)]
 └── Incident / Alert (High Priority)
         │
         ├──► [3. Notification Debouncer] ─► Hiển thị Toast / Sound (Giới hạn 1 lần / 5s)
         └──► [4. Bounded Event Store] ────► Cập nhật State (Cắt tối đa 100 phần tử)
```

---

## 4. Đặc tả kỹ thuật & Hướng dẫn triển khai

### 4.1. Phân luồng ưu tiên sự kiện (Priority Routing)
Phân loại các sự kiện `RealtimeEventType` thành 2 nhóm ưu tiên:

1. **Nhóm Khẩn cấp (High Priority)**:
   - Sự kiện: `INCIDENT_ALERT`, `INCIDENT_UPDATE`, `DETECTION_ALERT`.
   - Hành vi: Cập nhật state ngay lập tức vào bảng vụ việc; kích hoạt cảnh báo giao diện (Toast/Badge).
2. **Nhóm Dữ liệu nền (Low Priority)**:
   - Sự kiện: `METRIC_UPDATE`, `NETWORK_FEATURE_UPDATE`.
   - Hành vi: Đưa vào hàng đợi đệm (Batch Queue), không render ngay mà gom lại cập nhật theo chu kỳ.

---

### 4.2. Gom cụm & Điều tiết nhịp độ (Batching & Throttling Queue)
Tuyệt đối không gọi `setState` trực tiếp trong listener `onmessage` đối với dữ liệu telemetry.

**Quy chuẩn triển khai**:
- Sử dụng `useRef` để giữ hàng đợi tin nhắn đệm (`messageQueueRef`).
- Sử dụng đồng hồ chu kỳ (`setInterval` 500ms – 1000ms) để rút trích toàn bộ tin nhắn trong hàng đợi và gọi `setState` gộp duy nhất một lần.

```typescript
// dashboard/src/useInfrastructure.ts (Mẫu áp dụng)
const telemetryQueueRef = useRef<RealtimeMessage[]>([]);

const handleMessage = useCallback((message: RealtimeMessage) => {
  if (message.event === "metric_update") {
    // Đẩy vào hàng đợi đệm, không kích hoạt re-render
    telemetryQueueRef.current.push(message);
    return;
  }
  
  if (message.event === "incident_alert" || message.event === "detection_alert") {
    // Sự kiện khẩn cấp: cập nhật ngay kèm debouncer
    handleHighPriorityEvent(message);
  }
}, []);

// Flush chu kỳ 1000ms
useEffect(() => {
  const timer = setInterval(() => {
    if (telemetryQueueRef.current.length === 0) return;
    
    const batch = [...telemetryQueueRef.current];
    telemetryQueueRef.current = [];
    
    setSnapshot((prev) => applyTelemetryBatch(prev, batch));
  }, 1000);

  return () => clearInterval(timer);
}, []);
```

---

### 4.3. Thuật toán Reconnect: Exponential Backoff kết hợp Random Jitter
Khi mất kết nối WebSocket, cấm đặt thời gian thử lại cố định (ví dụ `3000ms`).

**Công thức tính thời gian chờ**:
$$\text{delay} = \min(\text{baseDelay} \times 2^{\text{attempt}}, \text{maxDelay}) + \text{random\_jitter}$$
Trong đó:
- $\text{baseDelay} = 1000\text{ ms}$ (1 giây).
- $\text{maxDelay} = 30000\text{ ms}$ (30 giây).
- $\text{random\_jitter} \in [0, 1000]\text{ ms}$.

```typescript
// dashboard/src/useWebSocket.ts (Mẫu chuẩn)
const retryAttemptRef = useRef(0);

function scheduleReconnect() {
  const baseDelay = 1000;
  const maxDelay = 30000;
  
  const expDelay = Math.min(baseDelay * Math.pow(2, retryAttemptRef.current), maxDelay);
  const jitter = Math.random() * 1000;
  const totalDelay = expDelay + jitter;
  
  retryAttemptRef.current += 1;
  setTimeout(connect, totalDelay);
}
```

---

### 4.4. Cơ chế đồng bộ bù đắp khi Reconnect (State Reconciliation)
Nguyên tắc bất biến:
> **WebSocket chỉ là tín hiệu báo tin (Signal). Database REST API mới là chân lý (Source of Truth).**

Khi WebSocket chuyển trạng thái từ `DISCONNECTED` sang `CONNECTED`:
1. Đặt lại `retryAttemptRef.current = 0`.
2. Lập tức kích hoạt âm thầm các hàm gọi REST API để kéo lại bức tranh toàn vẹn của hệ thống:
   - `fetchNodes()`: Cập nhật trạng thái sống/chết của máy chủ.
   - `fetchActiveIncidents()`: Kéo các sự cố đang mở (`status=DETECTED` hoặc `status=MITIGATING`) để bù đắp khoảng trống lúc offline.

```typescript
// dashboard/src/useInfrastructure.ts
const wasConnectedRef = useRef(false);

useEffect(() => {
  if (!wasConnectedRef.current && isConnected) {
    // Vừa kết nối lại sau khi bị mất mạng -> Tự động re-sync
    reconcileActiveState();
  }
  wasConnectedRef.current = isConnected;
}, [isConnected]);
```

---

### 4.5. Giới hạn dung lượng bộ nhớ trượt (Bounded Sliding Window)
Để tránh rò rỉ bộ nhớ (Memory Bloat) khi dashboard chạy liên tục 24/7 trên màn hình giám sát (NOC/SOC):

1. **Danh sách Events / Incidents**:
   - Chỉ lưu tối đa `MAX_EVENTS = 100` sự kiện gần nhất trên RAM frontend.
   - Khi có sự kiện mới, dùng `slice(0, MAX_EVENTS)` để loại bỏ các phần tử cũ nhất.
   - Tra cứu sự kiện cũ hơn phải thực hiện qua REST API phân trang (`Pagination`).
2. **Lịch sử đo đạc Metric (Telemetry Histories)**:
   - Chỉ lưu trữ dữ liệu trong cửa sổ trượt tối đa `15 phút` (tương đương 180 mẫu đo với tần suất 5s/mẫu).
   - Tự động cắt bỏ (`filter` / `slice`) các mẫu có `observed_at < now - 15 minutes`.

---

### 4.6. Chống bão chuông thông báo (Alert Notification Debouncing)
Để bảo vệ kỹ sư vận hành khỏi tình trạng Alert Fatigue:
- Nhóm thông báo theo khóa: `incident_key = ${project_id}_${node_id}_${title}`.
- Mỗi khóa chỉ được phép kích hoạt Toast Notification hoặc âm thanh tối đa **1 lần trong mỗi 5 giây**.
- Các sự kiện cùng loại phát sinh trong cửa sổ 5 giây chỉ làm tăng bộ đếm số lần (`badge counter: x5`) thay vì hiện thêm thanh toast mới.

---

## 5. Checklist nghiệm thu chất lượng (Quality Gate)

Trước khi nghiệm thu bất kỳ tính năng frontend nào có kết nối WebSocket, phải kiểm thử đạt các tiêu chí sau:

- [ ] **Stress Test (Chống đơ giao diện)**: Bắn giả lập 200 `metric_update` và 50 `detection_alert` mỗi giây vào kết nối WebSocket. Giao diện Dashboard vẫn phải duy trì tốc độ khung hình $\ge 50\text{ FPS}$, cuộn trang mượt mà, không giật lag.
- [ ] **Offline & Recovery Test**: Ngắt kết nối mạng (DevTools Network Offline) trong 30 giây, tạo sự cố mới trên Controller, sau đó bật lại mạng. Dashboard phải tự kết nối lại thành công và hiển thị đúng sự cố vừa tạo mà không cần F5.
- [ ] **Thundering Herd Test**: Khởi động lại Controller (`docker compose restart controller`). Kiểm tra log kết nối: các client kết nối lại rải rác theo hàm mũ, không có hiện tượng hàng trăm kết nối ùa vào cùng một mili-giây.
- [ ] **Memory Stability Test**: Mở Dashboard qua đêm (8 tiếng) với luồng telemetry chạy liên tục. Dung lượng RAM của tab trình duyệt không được tăng lũy tiến không giới hạn (duy trì ổn định dưới 200MB).
