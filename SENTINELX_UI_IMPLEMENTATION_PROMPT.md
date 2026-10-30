# Prompt triển khai SentinelX UI cho GPT-6.1-Sol

Ngày: 23/10/2026. Cập nhật V4 theo yêu cầu “ok chỉnh đi” sau đánh giá bảy ảnh bản sáng. V4 giữ palette/font V3 nhưng cho phép chỉnh phân cấp, khoảng cách, tên trạng thái và tương tác chart/log theo mục 15 của kế hoạch. Không còn áp khóa V3 “chỉ đổi màu, không chỉnh layout”. Đây là prompt dành cho phiên thực thi tiếp theo, không phải yêu cầu tự chạy code ngay khi đọc tài liệu.

## Cách dùng

Checkpoint mới nhất: V4 đã hoàn thành code; build/lint, 23 test UI, 29 JS module, 16 tổ hợp browser, Ruff, mypy110 files và pytest137 test PASS. Pytest có3 cảnh báo deprecation cũ. Bằng chứng/giới hạn nghiệm thu tại mục15.4; chưa kiểm tra toàn bộ Controller thật/screen reader/zoom200%. Đối chiếu yêu cầu mới và diff trước khi làm tiếp, không tự làm lại V4 hoặc toàn bộ P0–P6/paletteV3. Mục12–14 là lịch sử V1–V3. IBM Plex Mono tiếp tục dùng có chọn lọc cho IP/time/code và số tài nguyên trong bảng; KPI tổng hợp và hostname inventory/attention/ranking dùng sans.

Mở repository SentinelX trong IDE, chọn GPT-6.1-Sol nếu môi trường cung cấp model đó, rồi paste khối prompt bên dưới. Không cần paste toàn bộ lịch sử chat hoặc toàn bộ kế hoạch: model phải đọc file kế hoạch local. Prompt không tự thay được model hoặc reasoning setting của ứng dụng.

Phần tiết kiệm token đến từ scope rõ, đọc chọn lọc, quyết định thiết kế đã chốt và checkpoint để tiếp tục; không phải từ cam kết một model luôn tốn ít token hơn trong mọi tình huống.

## Prompt chính — sao chép nguyên khối

```text
Bạn đang triển khai tinh chỉnh UI/UX cho SentinelX, nền tảng giám sát hạ tầng Linux dùng React + Vite + TypeScript. Tôi cho phép sửa code frontend và test liên quan theo kế hoạch đã duyệt. Không chỉ lập lại kế hoạch.

NGUỒN SỰ THẬT
1. Đọc AGENTS.md và các tài liệu dự án bắt buộc theo routing, chỉ các mục liên quan frontend/Foundation hiện tại.
2. Đọc skill C:/Users/Trung Chau/.codex/skills/ui-ux-pro-max/SKILL.md trước công việc UI. Dùng skill có chọn lọc để thực hiện thiết kế đã duyệt, không tạo dashboard template mới, không cài/cập nhật lại skill.
3. Đọc SENTINELX_UI_REFINEMENT_PLAN.md. Đọc ràng buộc hiện hành mục 1–3 và đặc tả/checkpoint V4 mục 15 trước; đọc mục trang/dữ liệu liên quan khi cần. Mục 11–14 là lịch sử V1–V3, không phải PASS V4 hoặc chỉ thị khôi phục nền tối. Nếu có xung đột, mục 15 ưu tiên hơn khóa layout/type scale cũ. Không bỏ visual review để chỉ refactor logic FE.
4. Kiểm tra git status, branch và các file có thật. Giữ nguyên thay đổi có sẵn của tôi. Không giả định repository giống hệt lúc lập kế hoạch nếu file đã đổi.

MỤC TIÊU
Hoàn thành V4: thống nhất ý nghĩa trạng thái, đưa dữ liệu lên cao hơn bằng giảm lớp chrome/padding thừa, phân cấp khối tóm tắt với bảng thao tác, cải thiện chart tooltip và log filters. Giữ canvas #f5f6f7/panel trắng, graphite CTA/focus, link xanh tiết chế, logo, font family, thành phần bo tròn, metric card tách nhau và các section Tổng quan full-width từng hàng. Không trang trí bằng gradient/glow/hero hoặc biến công cụ vận hành thành website bán hàng.

CÁC QUYẾT ĐỊNH ĐÃ CHỐT
- Giữ nền sáng V3; không thay logo/framework/icon library, font source, dependency hoặc thêm theme toggle. V4 chỉnh bố cục có chọn lọc theo mục 15, không redesign toàn app hoặc quay lại nền đen/cyan.
- Giữ Be Vietnam Pro cho UI/tiêu đề và số KPI; IBM Plex Mono cho IP, timestamp, event code, token/lệnh và giá trị tài nguyên trong bảng. Hostname inventory/attention/ranking dùng sans; hostname log/selector kỹ thuật có thể mono. Số tổng hợp dùng sans-tabular, không monospace trang trí. Giữ fallback và font-display: swap.
- Palette V3: canvas #f5f6f7, panel #ffffff, sidebar/log #f9fafb, divider #e1e3e6, control border #7a838f. Chữ chính/phụ/muted #202124/#50565e/#626a73. Primary CTA #25282d (hover #3e4249), chữ trắng; link #3459c7 (hover #24469f), selection #eef1f5. CPU #147d73, RAM #6554c0; ổn định/chú ý/mất kết nối #17704d/#945d0b/#b93643 trên nền nhạt tương ứng tại mục 3.1. Kiểm tra contrast thực, không tái dùng tỷ lệ V2.
- Focus #4b5563, 2px, outline-offset 0, sát khung bo; không cyan/glow hoặc vòng sáng tách lớp. Giữ focus-visible cho bàn phím; composite search chỉ có viền wrapper, input không tạo viền thứ hai. Khai báo color-scheme: light và theme-color theo canvas; xử lý selected/nav/scrollbar/modal còn màu tối hardcoded.
- Typography desktop V4: body 15px/400, label 14px/500, metadata 13px/400, H1 28px/600 (thay 30px), section 16–17px/600, KPI 40px/600. Cho mobile/giá trị dài thích nghi có kiểm soát; giảm padding/chrome, không thu nhỏ toàn UI.
- Metric cards có gap 16px, bo tròn, số là tâm điểm; bỏ ONLINE/ATTENTION và màu trang trí dư thừa. Không ghép card thành strip liền.
- Tỷ lệ máy chủ ổn định, Máy chủ cần xử lý, Tổng hợp theo dự án, Máy chủ sử dụng tài nguyên nhiều nhất và Sự kiện gần nhất: mỗi section một hàng toàn chiều rộng, không ghép thành bento hai cột.
- KPI “Cần xử lý” cộng cảnh báo + mất kết nối + chờ đăng ký; pending đơn thuần dùng màu trung tính. Nhóm sức khỏe warn gọi “Cảnh báo”; nhãn của từng host phân biệt “Vượt ngưỡng” khi CPU >75% hoặc RAM >85%, “Suy giảm” khi Agent degraded nhưng không vượt ngưỡng. Không đổi logic phân loại hoặc giả degraded thành threshold violation.
- Tỷ lệ máy chủ ổn định vẫn = số ổn định / tổng host trong phạm vi, gồm pending; không đổi mẫu số để điểm đẹp hơn, không gọi là health score/SLA. Ranking là top host có mẫu hợp lệ, không khẳng định mọi host trong đó tải cao.
- Mỗi section có cấu trúc nội dung riêng: health summary + distribution/status trong cùng panel; attention dùng cột host → lý do → trạng thái/action; ranking dùng hostname → track có marker ngưỡng thật → giá trị. Không cap cả cụm ở nửa trái desktop rồi để nửa phải rỗng. Mobile stack logic, không ép bảng ngang cho attention.
- Inventory là bảng làm việc có cột chủ đích và số liệu dễ đọc; Telemetry là workspace phân tích một host với readout gần plot; Events là toolbar + vùng log, preview/full khác nhau. Không nhân bản cùng icon–title–card–footer cho mọi loại dữ liệu.
- Giảm các lớp chrome/header/footer lặp, không giảm font toàn bộ để nhồi thông tin. Lọc trạng thái đặt cạnh metadata scope; topbar là nơi nhận diện nguồn/kết nối cùng action kết nối Controller. Bỏ banner demo lặp trên mỗi trang nhưng vẫn ghi rõ mô phỏng. Trạng thái cập nhật/tạm dừng của log là trạng thái chức năng riêng, không được mất.
- Thêm máy chủ là primary ở trang Máy chủ, secondary ở Tổng quan; không phải primary action Telemetry/Nhật ký.
- Search focus bo theo khung ngoài; selector dự án có viền rõ; giữ keyboard accessibility.
- Máy chủ: row selection nhẹ, sort direction thực, hover không xóa selected, giữ view/sort trong phiên.
- Telemetry: một ngữ cảnh host, chart rộng thật, font trục cố định, CPU solid/RAM dashed; bỏ fill dày. Sửa nhãn thời gian chồng nhau bằng tick theo miền thời gian và collision avoidance, không chỉ giảm font hoặc ẩn toàn bộ trục.
- Telemetry: số lớn phía trên luôn là giá trị mới nhất; hover/focus lịch sử chỉ hiện giá trị tại mẫu trong tooltip gần x/crosshair, clamp trong khung, không che hoặc thay nghĩa readout mới nhất. Có đường đọc mẫu bằng bàn phím và thông báo ngữ cảnh phù hợp; giữ miền Y 0–100%.
- Nhật ký: bộ lọc Tất cả / Trạng thái & cảnh báo / Telemetry, mặc định Tất cả. Giữ event chưa biết trong Tất cả; nhãn dễ hiểu kèm raw event code. Search ghép với nhóm lọc; trạng thái cập nhật/tạm dừng hiện gần điều khiển. Full-page dùng một cuộn trang, controls/tên cột sticky có kiểm soát trên desktop; mobile không lồng cuộn. Preview chỉ cao theo số hàng. Pause chỉ đóng băng buffer hiển thị, ingestion vẫn chạy; đổi scope reset snapshot.
- Giữ wire contracts, REST/WS/demo, enrollment, Controller URL cấu hình và race guards. Không chỉnh backend, migrations hoặc milestone M1–M8.
- Missing là —, không phải 0; 0 thật hợp lệ. RX/TX là counter tích lũy, không gắn /s. Số mẫu 30/60/120 không gọi là số phút.
- Host Telemetry không tự đổi theo filter/realtime; reset filter không xóa project. Metric timestamp không thay bằng heartbeat.

CÁCH THỰC HIỆN
1. Tiếp tục V4 từ diff và checkpoint mục 15; không làm lại P0–P6/V2/V3. Chỉ hoàn thiện phần chưa xong của semantics, hierarchy, chart/log và kiểm chứng; không dùng khóa V3 chỉ đổi màu để từ chối các chỉnh sửa V4 đã được duyệt.
2. Trước mỗi bước, đọc đúng component/CSS/state liên quan. Không quét toàn bộ backend hoặc đọc lặp toàn bộ lịch sử chat. Dùng skill kiểm chứng hướng sáng và tương tác đã chốt, không khảo sát vô hạn để tìm template/palette khác.
3. Sửa thành patch nhỏ, giữ thiết kế hiện có, không viết lại toàn App hoặc thêm layer kiến trúc không cần thiết. Kiểm tra cascade trước khi thêm CSS override; không dùng !important hàng loạt.
4. Dùng thành phần và dependency đang có. Không cài library, đổi lockfile, thay API hoặc thêm tính năng ngoài kế hoạch để làm demo đẹp.
5. Không tạo host thật, không tự chạy lệnh enrollment, không commit/push/PR. Nếu branch không phù hợp, báo ràng buộc và chỉ tạo feature branch theo quy tắc dự án khi không ảnh hưởng thay đổi hiện hữu; không tự chuyển nhánh làm mất worktree.
6. Cập nhật bảng tiến độ V4 mục 15 sau mỗi bước bằng việc đã làm và bằng chứng ngắn; giữ nguyên nhật ký V1–V3 mục 12–14. Nếu phiên bị gián đoạn, tiếp tục từ checkpoint; không bắt đầu lại toàn bộ audit. Chưa kiểm tra thì ghi IN PROGRESS/NOT VERIFIED, không dùng PASS lịch sử thay thế.
7. Không mở sub-agent trừ khi thật sự cần và tiết kiệm được công việc lặp; ưu tiên một luồng thực thi gọn cho scope đã xác định.
8. Cập nhật cho tôi ngắn gọn sau mỗi phần có kết quả thực. Không chỉ hứa rồi phân tích kéo dài mà chưa lưu thay đổi. Không yêu cầu tôi duyệt lại các quyết định đã ghi rõ; chỉ hỏi khi thiếu quyền hoặc có xung đột làm thay đổi scope.

KIỂM CHỨNG
- Chạy baseline rồi chạy lại: npm.cmd --prefix dashboard run build; npm.cmd --prefix dashboard run lint; npm.cmd --prefix dashboard run test:ui. Chạy từng lệnh rõ ràng, ghi kết quả thật.
- Nếu có dev server, xác nhận đúng port và dùng test:dev theo kế hoạch. HTML 200/build pass không đủ; kiểm tra React mount, JS modules và runtime errors để tránh trang trắng.
- Tuân thủ quality gate AGENTS: uv run ruff check src tests; uv run mypy src tests; uv run pytest -v khi bàn giao. Báo riêng lỗi có sẵn/lỗi môi trường, không sửa backend ngoài scope để che lỗi.
- Kiểm tra cả bốn route và các modal liên quan ở 390, 768, 1366, 1920 CSS px; keyboard/focus, zoom 200%, zero/missing data, hostname dài, chart irregular timestamps, selection và scope changes.
- So sánh ảnh trước/sau cùng viewport và dữ liệu cố định khi có. V4 phải thấy dữ liệu sớm hơn, phân biệt pending với cảnh báo, giữ hierarchy/full-row và light theme. Kiểm tra tooltip gần điểm/clamp ở hai mép, readout mới nhất không đổi khi xem lịch sử, filter log mặc định All/unknown events/search/pause/scope và sticky không che focus. Nếu thiếu baseline deterministic, ghi giới hạn so sánh.
- Nếu browser/tool không kết nối, ghi NOT VERIFIED cho phần đó và tiếp tục các bước không bị chặn. Không thử lại vô hạn, không bịa screenshot hoặc kết quả PASS.
- Cập nhật test string cũ khi markup/copy thay đổi có chủ đích nhưng bảo toàn assertion về hành vi và ý nghĩa. Không xóa test để làm xanh.

ĐIỂM DỪNG VÀ BÀN GIAO
Hoàn thành V4 trong phạm vi mục 15 đã duyệt, bảo toàn palette/font V3 và các guardrails dữ liệu P0–P6. Không mở rộng sang milestone tiếp theo. Báo các file đổi, khác biệt thị giác chính, kết quả từng gate và phần chưa kiểm chứng theo format dự án, ngắn gọn nhất có thể. Không paste toàn bộ code vào câu trả lời nếu đã sửa trong workspace. Không gọi hoàn tất đầy đủ nếu còn lỗi thuộc scope hoặc verification bắt buộc chưa được thực hiện; phân biệt code đã xong với nghiệm thu chưa xong.

Bắt đầu bằng kiểm tra trạng thái repository và đọc tài liệu bắt buộc, rồi tiếp tục bước V4 chưa hoàn thành theo checkpoint. Không lập lại kế hoạch dài hoặc hỏi tôi có muốn bắt đầu không.
```

## Prompt tiếp tục nếu phiên bị gián đoạn

```text
Tiếp tục công việc UI SentinelX đang dở theo SENTINELX_UI_REFINEMENT_PLAN.md và SENTINELX_UI_IMPLEMENTATION_PROMPT.md.

Đọc AGENTS.md, skill UI/UX bắt buộc, git status/diff và đặc tả/checkpoint V4 mục 15 của kế hoạch. Xác định bước cuối có bằng chứng đã hoàn thành; đối chiếu diff thực trước khi tin checkpoint. Mục 11–14 là lịch sử V1–V3, không phải bằng chứng V4 hoặc yêu cầu quay lại nền tối. Không đọc lại toàn bộ repository hoặc tái lập kế hoạch.

Tôi tiếp tục cho phép triển khai frontend/test V4 tại mục 15: rõ nghĩa Cần xử lý/Cảnh báo/Vượt ngưỡng/Suy giảm, header gọn, một nguồn trạng thái ở topbar, H1 28px, tooltip lịch sử tách readout mới nhất, log có nhóm lọc và một vùng cuộn trang. Giữ nền sáng/fonts/radius/gap KPI/full-row, mọi guardrail dữ liệu và thay đổi không liên quan của tôi. Lưu patch/checkpoint sớm, kiểm tra tương ứng rồi hoàn thành V4 verification. Không tự commit/push, không mở rộng backend/milestone/dependency hoặc quay lại nền đen/cyan.

Nếu công cụ nào lỗi lặp lại, báo lỗi cụ thể và hoàn thành phần không bị chặn; không chỉ gửi một câu rồi chờ/phân tích vô hạn. Chỉ báo PASS khi có kết quả kiểm chứng; các phần chưa kiểm tra ghi NOT VERIFIED.
```

## Nếu muốn chia phiên để kiểm soát chi phí

Thêm một câu vào cuối prompt chính: “Phiên này chỉ hoàn thiện phần V4 còn thiếu theo checkpoint mục 15 và kiểm tra tĩnh; cập nhật bằng chứng rồi dừng, browser/visual verification dành cho phiên sau.” Phiên sau dùng prompt tiếp tục và ghi rõ điểm dừng mới. Đây là lựa chọn tùy người dùng, không phải bắt buộc dừng sau mỗi bước.

Không paste lại toàn bộ kế hoạch ở mỗi lượt. File local và checkpoint là nguồn ngữ cảnh bền vững; câu nhắc tiếp tục chỉ cần nêu bước đang làm và ràng buộc mới nếu có.
