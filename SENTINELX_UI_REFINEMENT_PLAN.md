# SentinelX — Kế hoạch tinh chỉnh UI/UX

Ngày lập: 23/10/2026. Trạng thái: V4 đã triển khai và kiểm chứng trong phạm vi mục 15.4. Palette/fonts V3 được giữ; mục 15 ưu tiên hơn các khóa layout/type scale ở mục cũ. Mục 12–14 giữ bằng chứng lịch sử V1–V3; các giới hạn nghiệm thu chưa kiểm tra vẫn được ghi riêng.

## 1. Mục tiêu và ranh giới

Tinh chỉnh giao diện giám sát hiện có thành một công cụ vận hành hạ tầng tinh tế, dễ đọc và có chủ đích. Theo yêu cầu mới V3, chuyển sang nền sáng trung tính, chữ và primary action graphite; giữ logo, bo góc, các metric card tách rời và từng phần Tổng quan chiếm trọn một hàng. Không thiết kế lại thành website thương mại, không áp dụng một dashboard template mới.

Tài liệu này là đặc tả bàn giao để model thực thi không phải suy đoán lại quyết định thiết kế. Đọc cùng SENTINELX_UI_IMPLEMENTATION_PROMPT.md. Phạm vi là tinh chỉnh dashboard hiện có trên nền Foundation F10–F14, không triển khai M1–M8.

Chỉ được bắt đầu chỉnh code khi người dùng giao nhiệm vụ triển khai. Việc tạo tài liệu này không phải xác nhận rằng giao diện hoặc kiểm thử đã hoàn thành.

**Lịch sử V2:** Người dùng đã cho phép thay đổi màu sắc, font chữ, kích thước và độ đậm nhạt sau khi xem V1. Bố cục theo nhiệm vụ và hệ chữ V2 được giữ; palette tối ở mục 13 là bằng chứng lịch sử, không còn ràng buộc hiện hành.

**Cập nhật V3 — nền tảng bảng màu:** Người dùng đã duyệt trắng–graphite. Khóa chỉ đổi palette/layout giữ nguyên áp dụng cho lượt V3, không ngăn các tinh chỉnh V4 đã được duyệt tại mục 15.

**Cập nhật V4 — ưu tiên mới nhất:** Sau bảy ảnh bản sáng và đánh giá tiếp theo, người dùng yêu cầu “ok chỉnh đi”. Giữ light theme, font, card bo/tách rời, full-row sections; chỉnh hierarchy, khoảng cách, nhãn trạng thái và tương tác chart/log. Đặc tả và bằng chứng hiện hành tại mục 15.

### 1.1 Nguồn đánh giá

- Bảy ảnh người dùng gửi: Tổng quan đầu/giữa/cuối trang, Máy chủ, Telemetry đầu/cuối trang và Nhật ký sự kiện.
- Năm ảnh phản hồi sau V1: Tổng quan đầu/cuối, Máy chủ, Telemetry và Nhật ký. Người dùng nhận xét bản mới chỉ đẹp/gọn hơn nhưng chưa khác về bản sắc; chữ vẫn nhỏ so với diện tích, các panel vẫn đồng dạng, attention/ranking để vùng trống lớn bên phải. Đây là cơ sở thiết kế V2, không phải yêu cầu đổi sang template hoặc trang giới thiệu sản phẩm.
- Kiểm tra cấu trúc React + Vite + TypeScript, CSS và luồng dữ liệu hiện tại. Đối chiếu lại tên file ở đầu phiên triển khai nếu repository đã thay đổi.
- Hướng dẫn local ui-ux-pro-max, áp dụng có chọn lọc cho sản phẩm giám sát đã có thiết kế được duyệt.
- Ảnh là bằng chứng thị giác, không phải bằng chứng rằng tương tác, bàn phím hoặc responsive đã được kiểm thử. Ảnh đã được thu nhỏ; không suy ra CSS pixel trực tiếp từ pixel trong ảnh.

### 1.2 Điều bắt buộc giữ

- Canvas sáng trung tính #f5f6f7, panel trắng; primary action/focus graphite. Không quay lại khóa nền đen của V1/V2, không phủ trắng tinh toàn màn hình hoặc xanh navy toàn trang.
- Logo SentinelX và bộ icon hiện tại. Được đổi font theo cặp đã chốt ở mục 3.2; không sinh logo mới hoặc thay icon library.
- Metric card độc lập, có khoảng cách, bo tròn và tương phản vừa đủ với canvas.
- Các phần lớn của Tổng quan nằm nối tiếp, mỗi phần full-width: Sức khỏe toàn cụm, Máy chủ cần chú ý, Tổng hợp theo dự án, Máy chủ tải cao, Sự kiện gần nhất.
- Không ghép các phần trên thành bento hai hoặc ba cột để tiết kiệm chiều cao.
- Tổng quan trả lời tình hình toàn phạm vi; Telemetry phân tích một máy chủ. Không biến hai trang thành bản sao của nhau.
- Ô chọn dự án có khung rõ. Search focus bao quanh toàn ô gồm icon/input, không tạo viền vuông chỉ quanh phần input bên trong.
- Chữ và vùng thao tác dễ nhìn; giảm sự lặp lại và khoảng trống không có mục đích, không thu nhỏ tất cả để nhồi dữ liệu.
- Controller URL phải cấu hình được; giữ khả năng multi-host, REST query + WebSocket realtime.

### 1.3 Không nằm trong phạm vi

- Backend, migration, wire contract mới, authentication mới hoặc các milestone tiếp theo.
- Thay framework, chart library, state library hoặc cài dependency chỉ để làm đẹp. Đổi nguồn font bằng cơ chế tải font hiện có được phép; không cần thêm font package.
- Thêm uptime/SLA, điểm sức khỏe tự chế, incident, dự báo, sparkline giả, tốc độ mạng suy ra từ counter không đủ dữ liệu.
- Landing page, hero, slogan lớn, pricing, onboarding dạng quảng cáo, gradient trang trí, glassmorphism, glow, animation liên tục.
- Commit, push, tạo PR hoặc sửa các thay đổi không liên quan của người dùng.

## 2. Chẩn đoán thị giác từ ảnh

Chẩn đoán ảnh gốc V1/V2: vấn đề không phải là thiếu màu hoặc thiếu hiệu ứng, mà là nhiều lớp khung giống nhau, thông tin lặp và cấu trúc không phân biệt nhiệm vụ. V3 bổ sung phản hồi về nền tối và focus cyan; chuyển sáng không thay thế các cải thiện bố cục V2 đã thực hiện.

### 2.1 Danh mục ảnh tham chiếu

| Mã | Nội dung ảnh | Bằng chứng chính |
| --- | --- | --- |
| S1 | Tổng quan, phần đầu | Nhiều dải điều hướng/filter/demo trước dữ liệu; KPI và sức khỏe lớn, danh sách cần xử lý nằm dưới màn hình đầu |
| S2 | Máy chủ | Tiêu đề trang và tiêu đề panel trùng ý; hàng được chọn xanh đậm toàn chiều ngang; bảng ba hàng không cần nội dung giả để lấp trống |
| S3 | Telemetry, phần đầu | Nút Thêm máy chủ và filter chung không sát nhiệm vụ; selector host, header chart, hostname lặp thành nhiều tầng |
| S4 | Tổng quan, phần giữa | Sức khỏe toàn cụm có nhiều khung con và footer; panel nào cũng có dải header giống nhau; thông tin trong hàng bị kéo xa nhau |
| S5 | Tổng quan, phần cuối | Thanh tải rất dài; preview sự kiện chỉ một dòng nhưng có vùng rỗng lớn; nguồn dữ liệu lặp nhiều nơi |
| S6 | Telemetry, biểu đồ đầy đủ | Nhãn thời gian cuối trục X chồng lên nhau; plot hẹp so với khung; hai vùng tô tạo màn màu; chữ trục và hình học bị scale |
| S7 | Nhật ký sự kiện | Vùng log bị giới hạn chiều cao, phải cuộn lồng; nhiều metric_update giống nhau; chrome và nguồn dữ liệu vẫn lặp |

Không có đường dẫn ảnh local được xác nhận. Model thực thi dùng mô tả trên và chụp lại UI hiện tại; không giả định tồn tại file screenshot trong repository.

### 2.2 Các vấn đề và quyết định sửa

| ID | Hiện trạng | Vì sao chưa tinh tế | Quyết định cụ thể |
| --- | --- | --- | --- |
| V01 | Breadcrumb, tiêu đề, subtitle, filter, trạng thái live, demo banner nối nhau | Phần quản trị giao diện tranh diện tích với nội dung vận hành | Bỏ breadcrumb phẳng không cung cấp điều hướng; gom scope vào tiêu đề phụ; chỉ giữ toolbar cần cho từng trang |
| V02 | Cùng một nút Thêm máy chủ nổi bật trên mọi trang | Hierarchy theo template, không theo việc người dùng đang làm | Primary action ở Máy chủ; Tổng quan dùng secondary; không đặt action này trong header Telemetry/Nhật ký |
| V03 | Panel nào cũng có icon, badge, header nền khác và footer | Mọi phần đều có trọng lượng thị giác như nhau | Dùng header cùng nền panel, chỉ thêm action/count khi có giá trị; không tạo footer chỉ để lặp nguồn dữ liệu |
| V04 | Label KPI in hoa, trạng thái tiếng Anh và số monospace lớn cùng cạnh tranh | Cảm giác console trang trí; đọc tiếng Việt không liền mạch | Label sentence case; bỏ ONLINE/ATTENTION dư thừa; số là tâm điểm, metadata một cấp thấp hơn |
| V05 | Card cảnh báo tô vàng toàn khối và nhiều icon màu | Màu mất ý nghĩa ưu tiên | Card nền trung tính; màu cảnh báo tập trung ở số/badge hoặc viền nhẹ, không phủ màu đậm cả card |
| V06 | Sức khỏe có panel, status box, footer link lồng nhau | Khung nhiều hơn thông tin | Giữ một panel full-width; status là nhóm thao tác phẳng; link danh sách nằm trong header |
| V07 | Hàng chú ý và ranking kéo nội dung ra hai đầu rất xa | Mắt phải quét dài để nối host với nguyên nhân/chỉ số | Dùng cột rõ, đưa giá trị sát thanh đo; giới hạn chiều dài track có chủ đích |
| V08 | Bảng dùng nhiều xanh, icon server và badge cùng lúc | Selection, link và status bị trộn | Chọn hàng bằng nền nhẹ riêng; V3 dùng #eef1f5; hostname là điểm liên kết chính, icon phụ trung tính |
| V09 | Telemetry có nhiều hàng giới thiệu, chart phủ màu dày | Dữ liệu chưa thật sự là trung tâm | Một hàng ngữ cảnh host; chart rộng, đường nét rõ, tô rất nhẹ hoặc không tô |
| V10 | Nhãn cuối trục thời gian chồng lên nhau | Lỗi trực tiếp ảnh hưởng khả năng đọc dữ liệu | Tick theo miền thời gian thực, có kiểm tra khoảng cách nhãn; không chọn tick theo chỉ số mẫu |
| V11 | Một event preview vẫn chiếm vùng cao; full log lại quá thấp | Cùng component nhưng không có hai chế độ layout phù hợp | Preview theo nội dung tối đa năm hàng; trang Nhật ký dùng vùng đọc lớn riêng |
| V12 | Dữ liệu mô phỏng/live/nguồn xuất hiện ở nhiều chỗ | Nhắc lại trạng thái khiến UI ồn nhưng không thêm tin cậy | Một trạng thái kết nối chuẩn ở header và một thông báo demo gọn; bỏ footer nguồn trùng |
| V13 | Chữ metadata nhiều chỗ 10–11px, ALL CAPS/mono dùng rộng | Trông kỹ thuật nhưng khó đọc, đặc biệt tiếng Việt | Nội dung quan trọng 14–15px; metadata 12–13px; mono chỉ cho dữ liệu kỹ thuật |
| V14 | Workspace card, số đếm sidebar, v0.1/F14 chiếm diện tích | Giống bản demo kỹ thuật hơn sản phẩm vận hành | Identity workspace gọn, không giả tương tác; chuyển phiên bản/milestone vào trợ giúp |

## 3. Hệ thống thị giác đích

### 3.1 Màu và độ tương phản

Palette V3 được người dùng duyệt: **trắng–graphite, màu dành cho dữ liệu**. Canvas xám trắng tách khỏi panel trắng; liên kết dùng xanh tiết chế, primary button và focus dùng graphite riêng. Không glow/gradient, không shadow quanh mọi card. Các mã dưới đây đối chiếu token triển khai ở dashboard/src/index.css; phải kiểm tra tương phản trên cặp màu thực tế, không coi việc có token là đã đạt accessibility.

| Vai trò | Mốc đề xuất | Cách dùng |
| --- | --- | --- |
| Canvas | #f5f6f7 | Xám trắng, không trắng tinh toàn viewport |
| Sidebar / vùng log | #f9fafb | Surface trung tính sáng |
| Panel/card / modal | #ffffff | Nền dữ liệu mặc định |
| Header bảng / hover | #f8f9fa / #f1f3f5 | Phân lớp nhẹ, không tạo dải nền đậm |
| Divider trang trí | #e1e3e6 | Phân vùng, không dùng làm dấu hiệu duy nhất để nhận ra input |
| Viền control | #7a838f | Select/input nhận diện rõ trên nền sáng |
| Chữ chính | #202124 | Giá trị và nội dung cần đọc |
| Chữ phụ / muted | #50565e / #626a73 | Không xám quá nhạt hoặc giảm opacity tùy tiện |
| Primary action / hover | #25282d / #3e4249 | Nút graphite, chữ trắng; tách khỏi token liên kết |
| Focus | #4b5563 | Viền trung tính 2px sát khung, outline-offset 0; không cyan/glow |
| Link / hover | #3459c7 / #24469f | Xanh tiết chế cho liên kết, không phủ lên mọi icon/card |
| Selected / accent subtle | #eef1f5 / #eef2fa | Selection phân biệt với hover và trạng thái sức khỏe |
| CPU / RAM | #147d73 / #6554c0 | Teal / violet đậm hơn cho nền trắng; solid / dashed giữ nguyên |
| Ổn định | #17704d trên #ecf6f0 | Border #b8d9c6; có text/icon đi kèm |
| Chú ý | #945d0b trên #fff5e5 | Border #e7cca0; không vàng nhạt khó đọc |
| Mất kết nối | #b93643 trên #fff0f1 | Border #e8b8be; không chỉ dựa vào màu |
| Trung tính / chưa có mẫu | #636b75 trên #eff1f3 | Border #cdd2d7; missing vẫn là — |

- Màu chữ thường tối thiểu 4.5:1; phần đồ họa và dấu hiệu tương tác thiết yếu tối thiểu 3:1 theo ngữ cảnh.
- Border trang trí không nhất thiết đạt 3:1, nhưng control không được chỉ dựa vào border quá mờ để nhận diện.
- Không shadow/glow quanh mọi card. Modal có thể có một lớp shadow nhẹ để phân biệt độ nổi.
- Không đổi màu CPU theo tình trạng cảnh báo trong chart khiến legend mất ổn định; cảnh báo dùng annotation/badge riêng.
- Khai báo color-scheme: light và theme-color theo canvas; kiểm tra native select/input, scrollbar, modal scrim và màu hardcoded còn sót. Không đảo màu logo/ảnh hoặc dùng CSS filter để giả light theme.
- Search focus nằm trên khung bo ngoài; không có vòng cyan tách lớp hoặc outline thứ hai quanh input. Giữ focus-visible cho người dùng bàn phím, không xóa chỉ để trông tối giản.

### 3.2 Typography và kích thước

V3 giữ hệ chữ V2: **Be Vietnam Pro** cho UI, tiêu đề, nhãn và số KPI; **IBM Plex Mono** cho IP, timestamp, event code, token/lệnh và giá trị tài nguyên trong bảng. Hostname trong inventory/attention/ranking dùng sans 15px/500; hostname trong log và selector kỹ thuật có thể dùng mono. Không dùng monospace cho mọi con số để giả cảm giác console. Số KPI lớn và giá trị tổng hợp dùng sans với font-variant-numeric: tabular-nums để realtime không làm cột nhảy chiều rộng. Tải qua cơ chế font hiện có, có fallback system sans/monospace và font-display: swap; kiểm tra dấu tiếng Việt, không thêm package.

| Thành phần | Kích thước đích | Ghi chú |
| --- | --- | --- |
| H1 trang | 30px / line-height 1.35 | Weight 600, không hero size; mobile 25px |
| Tiêu đề section | 17px / 1.4 | Weight 600, sentence case, không cần icon ở mọi tiêu đề |
| Nội dung chính | 15px / 1.5 | Weight 400; hostname và nội dung event dễ đọc |
| Label/control | 14px / 1.5 | Weight 500; không viết hoa toàn bộ để thay hierarchy |
| Metadata | 13px / 1.45 | Weight 400; không dùng 10px cho thông tin cần thao tác |
| Số KPI | 40px / 1.15–1.2 | Sans, weight 600, tabular; giảm có chọn lọc cho giá trị dài/mobile |
| Đơn vị KPI | 17px | Cùng baseline, không ngang cấp con số |
| Nhãn trục chart | 12–13px cố định | Không tăng theo tỷ lệ SVG |
| Input mobile | Tối thiểu 16px | Tránh zoom tự động khi focus |

Mono dành cho dữ liệu kỹ thuật có chọn lọc, không cho toàn bộ label/navigation hoặc KPI tổng hợp. Không làm toàn UI nhỏ lại để giảm chiều cao. Số lớn và nhịp chữ phải khác rõ V1 ở ảnh cùng viewport, không chỉ thay tên font trong token.

### 3.3 Khoảng cách, bo góc và khung

- Card/panel radius 18px; modal 24px; control 10px. Không dùng radius 24px cho mọi thành phần nhỏ.
- Main padding 28px desktop, 16px mobile. Gap giữa metric card 16px; giữa các section lớn 24px.
- Panel padding nội dung 20–24px. Header thường cao theo nội dung khoảng 60–64px, không ép cao nếu chỉ có một dòng chữ.
- Control thường cao 40px desktop, tối thiểu 44px trên mobile; icon 16–20px trong hit area thoải mái. Đây là mục tiêu tiện dụng, không gọi 44px là yêu cầu WCAG AA phổ quát.
- Giữ bảng đủ cao để đọc: hàng host khoảng 72–76px, hàng event khoảng 52–56px tùy nội dung. Nội dung dài được wrap có kiểm soát, không ép mất chữ.
- Khung lớn full-width không có nghĩa nội dung bên trong phải bị kéo xa nhau. Dùng grid/cột và max-width cho track để tổ chức thông tin.
- Header panel cùng nền body; table header được phép có nền phân biệt nhẹ. Không tạo ba dải nền header/body/footer cho mọi panel.

### 3.4 Copy và icon

- Dùng tiếng Việt nhất quán: Máy chủ trực tuyến, Cần chú ý, CPU trung bình, RAM trung bình, Mạng tích lũy.
- Giữ các thuật ngữ CPU, RAM, RX, TX, Telemetry, hostname và event code khi chúng có ý nghĩa kỹ thuật.
- Bỏ nhãn ONLINE/ATTENTION khi nhãn và màu đã diễn đạt cùng thông tin. Không đổi event code gốc; có thể kèm mô tả tiếng Việt.
- Icon điều hướng có ý nghĩa được giữ. Icon trang trí lặp trong mỗi header/card có thể bỏ hoặc chuyển trung tính.
- Không dùng mũi tên mở tab mới cho thao tác chỉ chuyển trang nội bộ nếu gây hiểu nhầm. Chọn chevron cho drill-down nội bộ; icon external-link chỉ dùng khi thật sự mở tài nguyên ngoài.
- Trạng thái demo phải luôn rõ ràng; không tô dấu xanh và gọi mô phỏng là kết nối Controller thật.

## 4. Shell dùng chung: giảm lặp nhưng không mất ngữ cảnh

### 4.1 Sidebar

1. Giữ logo và tên SentinelX. Thu gọn hoặc bỏ dòng OBSERVABILITY CONSOLE đang xuống hai dòng; tên sản phẩm và menu đã thể hiện chức năng.
2. Workspace identity là cụm thông tin nhỏ, tối đa hai dòng. Nếu không có thao tác chuyển workspace thật thì không vẽ như một card/button có thể click.
3. Giữ bốn mục Tổng quan, Máy chủ, Telemetry, Nhật ký sự kiện. Mục đang mở có nền selected trung tính nhẹ và aria-current; không cần khung xanh mạnh.
4. Giữ số máy chủ cạnh mục Máy chủ nếu hữu ích. Bỏ khối số đếm WORKSPACE lặp cùng dữ liệu với nội dung trang; không thay bằng widget mới.
5. Chuyển v0.1/F14 vào khu vực trợ giúp hoặc thông tin phiên bản nếu có. Không thêm modal mới chỉ để chứa version.
6. Giữ navigation responsive hiện hữu làm nền: full sidebar, icon rail ở tablet, điều hướng gọn ở mobile. Không xóa nhãn accessible khi thu gọn.

### 4.2 Topbar và search

- Topbar giữ ba nhiệm vụ: chọn phạm vi dự án, tìm hostname/IP, thể hiện trạng thái kết nối và thao tác cấu hình/làm mới có sẵn.
- Ô chọn dự án có viền control rõ, text không bị cắt mất toàn bộ tên dài; có accessible name. Không biến thành breadcrumb không khung.
- Search là một control bao gồm icon, input và shortcut hint. Focus-within tạo outline bo đúng khung ngoài; input bên trong không có outline thứ hai. Chỉ bỏ outline trong khi khung ngoài có thay thế nhìn thấy được.
- Shortcut '/' không chiếm phím khi người dùng đang gõ trong input/textarea/contenteditable; giữ hành vi này nếu đã có.
- Không gom nhiều icon không nhãn. Icon-only cần accessible name và tooltip nếu cơ chế tooltip có sẵn; không thêm thư viện.
- Trạng thái kết nối chuẩn ở đây: mô phỏng, đang kết nối, đã kết nối, mất kết nối. Trạng thái socket không đồng nghĩa mọi metric đều mới.
- Chỉ giữ một banner demo gọn trong nội dung khi cần giải thích chưa kết nối Controller, kèm action kết nối hiện có. Bỏ nguồn dữ liệu trùng trong từng footer và sidebar.

### 4.3 Page header và toolbar theo nhiệm vụ

| Trang | Header | Toolbar | Action nổi bật |
| --- | --- | --- | --- |
| Tổng quan | Tổng quan hạ tầng + phạm vi/số host | Lọc trạng thái nếu có tác dụng thật; reset chỉ khi đang lọc | Thêm máy chủ dạng secondary |
| Máy chủ | Danh sách máy chủ + tổng số trong phạm vi | Trạng thái, chế độ bảng/lưới; search dùng topbar | Thêm máy chủ primary |
| Telemetry | Telemetry tài nguyên + ngữ cảnh host | Host selector và số mẫu; không lặp filter trạng thái/vai trò của fleet | Chi tiết máy chủ dạng text/secondary |
| Nhật ký | Nhật ký hệ thống + phạm vi | Tìm sự kiện/hostname và tạm dừng hiển thị | Tạm dừng/Tiếp tục, không có primary Thêm máy chủ |

- Bỏ breadcrumb Infrastructure nếu chỉ là nhãn không có điều hướng phân cấp thực. Dự án vẫn hiện trong topbar.
- Subtitle không lặp cả tên dự án ở ba nơi. Giữ một câu scope ngắn, không slogan.
- Không hiện Xóa bộ lọc khi không có filter phụ đang bật. Reset không đổi dự án đang chọn.
- Vai trò suy đoán từ hostname không phải dữ liệu role chính thức. Bỏ filter vai trò khỏi toolbar chính; không sửa backend để hợp thức hóa nó. Metadata suy đoán nếu còn hiển thị phải được phân biệt với dữ liệu hệ thống.
- Khi chuyển route, trạng thái bảng/lọc phù hợp được giữ trong phiên. Không thêm localStorage nếu không có yêu cầu lưu qua lần truy cập.

## 5. Đặc tả từng trang

### 5.1 Tổng quan: tình hình và việc cần xử lý

Thứ tự cố định: header/toolbar gọn → demo notice nếu có → KPI → sức khỏe → máy chủ cần chú ý → tổng hợp dự án → tải cao → sự kiện gần nhất. Không chuyển section lớn thành hai cột.

#### A. Metric cards

- Giữ năm card ở desktop khi đủ rộng, gap 16px. Tự chuyển ba/hai/một cột theo min-width thực tế; không ép năm card trên tablet.
- Mốc chiều cao nội dung thường 152–176px, không dùng fixed height làm cắt metadata. Số 40px/600 sans-tabular; padding khoảng 20px, metadata 13px.
- Mỗi card có label, giá trị + đơn vị, tối đa một hoặc hai dòng metadata có nghĩa. Không icon, badge và nhãn tiếng Anh cùng mô tả một trạng thái.
- Máy chủ trực tuyến: số online/tổng; dòng phụ nêu offline và chờ đăng ký, không dùng progress bar giả.
- Cần chú ý: giữ rõ tổng số host cần xử lý có thể gồm chờ đăng ký; dòng phụ tách số vượt ngưỡng/degraded và số chờ đăng ký. Không khiến người dùng hiểu tất cả là sự cố đang chạy.
- CPU/RAM trung bình: hiển thị số host có mẫu hợp lệ; track nhẹ, nhất quán màu CPU/RAM và marker ngưỡng thật 75%/85%; không bịa trend so với hôm qua.
- Mạng tích lũy: tổng RX + TX của dữ liệu hợp lệ, cùng đơn vị thích hợp; dòng phụ RX/TX. Không gọi là băng thông hoặc MB/s.
- Card warning giữ nền trung tính hoặc tint amber rất nhẹ khoảng 3–4%; không dùng toàn nền vàng nâu như điểm nhấn trang trí. Màu số và label trạng thái đủ làm nổi bật.

#### B. Sức khỏe toàn cụm

- Một panel full-width, header có tiêu đề và link Xem máy chủ. Không footer full-width chỉ chứa link đó.
- Bên trong cùng panel full-row: vùng summary tỷ lệ ổn định + số ổn định/tổng ở trái; vùng distribution và status controls ở phải. Hai vùng này là cấu trúc nội dung của một section, không phải hai section đặt cạnh nhau. Mobile stack theo thứ tự summary → distribution → controls. Không gọi tỷ lệ này là SLA hoặc uptime.
- Thanh phân bố một hàng, màu có legend text. Không bỏ các nhóm 0 một cách khiến người dùng khó so sánh trạng thái.
- Status controls là nhóm phẳng: chấm màu, nhãn, số; vùng click đủ lớn, hover/focus rõ. Không vẽ bốn card đen có viền mạnh bên trong panel.
- Nếu thêm trạng thái frontend Chưa có mẫu, có thêm mục trong legend/filter và phép tính tổng. Wrap ở viewport hẹp, không giấu mất nhóm.
- Chiều cao tham chiếu khoảng 200–240px với nội dung thông thường; không ép fixed height. Giảm do bỏ lớp khung/footer, không do giảm font.
- Click nhóm trạng thái chuyển sang Máy chủ với filter tương ứng trong cùng dự án. Back không làm mất scope.

#### C. Máy chủ cần chú ý

- Mỗi hàng trình bày hostname, nguyên nhân cụ thể, trạng thái và drill-down. Ví dụ CPU 82.3% > 75%, chưa hoàn tất đăng ký; không dùng câu chung chung Hệ thống có vấn đề.
- Desktop dùng cột host/định danh → lý do cụ thể → trạng thái/action có nhãn. Không giữ toàn bộ nội dung ở nửa trái rồi để nửa phải trống do max-width cố định. Mobile xếp hostname, lý do và action thành nhóm dễ đọc; không tạo bảng ngang bắt buộc cho danh sách chú ý.
- Xếp offline trước, degraded/vượt ngưỡng tiếp theo, chờ đăng ký sau; trong cùng nhóm có thứ tự ổn định, tránh nhảy hàng theo từng phần trăm realtime.
- Không có vấn đề: một empty state gọn có text Tất cả máy chủ trong phạm vi hiện không cần xử lý, không minh họa lớn hoặc confetti.
- Không hide panel chỉ vì đang lọc ra 0 host; phải phân biệt Không có máy chủ phù hợp với Hệ thống ổn định.

#### D. Tổng hợp theo dự án

- Panel full-width, header nhẹ, không icon thư mục/badge nếu đã dư thừa.
- Khi chọn tất cả dự án: giữ bảng tổng hợp theo dự án.
- Khi chọn một dự án: vẫn có thể giữ một hàng tóm tắt theo yêu cầu người dùng, nhưng không phóng to hàng hoặc thêm khung trang trí để lấp chỗ.
- Cột số canh phải; số online/tổng, cần chú ý, CPU/RAM có đơn vị và missing state rõ. Không tính mẫu thiếu thành 0.

#### E. Máy chủ tải cao

- Panel một hàng toàn chiều rộng; toggle CPU/RAM ở header.
- Mỗi dòng dùng thứ hạng, hostname, track, phần trăm và drill-down theo cột nhất quán.
- Tách cột hostname khỏi track: thứ hạng → hostname → track → giá trị → drill-down. Track linh hoạt trong cột có giới hạn hợp lý; giá trị ở sát track. Không cap toàn bộ cụm hostname/track ở 640px khiến một nửa hàng desktop rỗng.
- Track có marker ngưỡng thật tương ứng CPU 75% hoặc RAM 85%, kèm giải thích ngưỡng ở header. Không giãn thanh tới hàng nghìn pixel hoặc thêm widget/dữ liệu giả để lấp diện tích.
- Tối đa năm host có mẫu hợp lệ; không thêm host giả. Thiếu mẫu không vào ranking; số 0 thật vẫn hợp lệ.

#### F. Sự kiện gần nhất

- Preview tối đa năm sự kiện đáng chú ý theo logic hiện có. Không biến thành bản sao toàn bộ log metric_update.
- Cao theo số hàng; một sự kiện không để vùng rỗng cao hơn nhiều hàng dữ liệu.
- Header có link Mở nhật ký. Không thanh nguồn dữ liệu riêng khi header app đã có.
- Timestamp, loại sự kiện, hostname, mô tả theo cột vừa đủ; trên mobile chuyển bố cục hàng xếp dọc có nhãn.

### 5.2 Máy chủ: bảng làm việc, không phải bộ thẻ quảng cáo

1. Dùng bảng làm mặc định. Giữ chế độ lưới hiện hữu nếu có, không xóa tính năng chỉ vì ảnh đang ở bảng.
2. Loại bỏ subtitle panel lặp với page header. Header panel chỉ cần count/kết quả lọc và toggle bảng/lưới khi hữu ích.
3. Tên host 15px, IP/metadata 13px; mono chỉ cho định danh kỹ thuật. Hostname dài wrap hoặc ellipsis có cách xem đầy đủ, không làm CPU/RAM bị ép mất.
4. CPU/RAM: sans-tabular dễ đọc, track ngắn cạnh hoặc dưới giá trị; chiều rộng cột ổn định; cột số canh phải nhất quán. Chủ động chia cột desktop theo nhiệm vụ: định danh rộng nhất, trạng thái đủ nhãn, CPU/RAM tương đương, action hẹp. Không để auto table sizing tạo khoảng trống ngẫu nhiên.
5. Hàng đang chọn: nền selected #eef1f5 theo V3, không mảng xanh đậm chiếm cả bảng. Hover của hàng đã chọn giữ dấu hiệu selected, không bị selector CSS ghi đè.
6. Chỉ một action drill-down rõ cho mỗi hàng; hỗ trợ bàn phím bằng link/button thật. Không chỉ gắn onClick vào tr mà không có đường truy cập bằng phím.
7. Sorting có icon hướng tăng/giảm thực và aria-sort. Icon hai chiều chỉ dành cho cột chưa active. Thứ tự ổn định khi giá trị bằng nhau.
8. Giữ sort, view mode và host đang chọn khi mở chi tiết rồi quay lại. Lưu trong state của route/app nếu component bị unmount, không thêm persistence dài hạn.
9. Không có kết quả: nêu rõ do filter và cho reset filter, không mở onboarding thêm host nếu dự án vẫn có máy chủ.
10. Ba host chỉ hiển thị ba hàng. Khoảng trống canvas dưới bảng là hợp lý; không tạo card hoặc kéo dãn hàng để lấp.

### 5.3 Telemetry: tập trung vào một máy chủ và diễn biến thời gian

#### A. Ngữ cảnh và bố cục

- Một hàng ngữ cảnh host gồm selector, IP/trạng thái và action chi tiết. Không lặp hostname trong subtitle trang, selector và một header chart riêng ba lần.
- Không dùng nút Thêm máy chủ hoặc filter trạng thái fleet như thao tác chính.
- Chart CPU/RAM là panel dữ liệu chính full-width. Disk/RX/TX đặt thành ba metric card độc lập bên dưới khi đủ rộng, stack khi hẹp.
- Legend và giá trị CPU/RAM đặt gần chart; phân biệt Giá trị mới nhất với giá trị tại điểm đang xem.
- V2 làm rõ workspace phân tích: host/context gọn phía trên, cặp readout CPU/RAM gần chart có số sans-tabular dễ đọc, plot là trọng tâm. Không áp cùng bố cục KPI fleet vào telemetry hoặc thêm số liệu tổng hợp không có dữ liệu thật.
- Selector 30/60/120 là số mẫu, không đổi nhãn thành phút. Việc chuyển sang time-range query thật là phạm vi khác, không giả lập bằng cách đổi tên.

#### B. Sửa biểu đồ ở mức hình học

1. Đo chiều rộng container bằng ResizeObserver hoặc cơ chế sẵn có. Dùng kích thước pixel thực cho plot, không scale toàn SVG viewBox cố định khiến chữ, nét và gutter bị phóng.
2. Plot cao khoảng 280–320px desktop, 240px mobile; gutters tham chiếu trái 48–56px, phải 16px, dưới 32px. Không tạo lề trái trống hàng trăm pixel.
3. Trục Y CPU/RAM là 0–100%; nhãn 0/25/50/75/100 hoặc giảm tick trên màn nhỏ nếu cần. Không co miền Y để làm biến động nhỏ trông nguy hiểm hơn.
4. Stroke CPU khoảng 2px nét liền; RAM khoảng 2px nét đứt; màu series cố định và legend không chỉ dựa vào màu.
5. Bỏ area fill RAM. CPU có thể không fill hoặc fill alpha tối đa khoảng 0.06; không dùng hai gradient chồng thành màn xanh.
6. Grid mảnh, tương phản vừa đủ; không mạnh hơn đường dữ liệu. Không animation path mỗi lần nhận mẫu realtime.
7. Trục X tính tọa độ từ observed_at trên miền thời gian. Tick chia đều theo thời gian thực, không lấy mẫu đầu/giữa/cuối theo index khi khoảng lấy mẫu không đều.
8. Số tick theo chiều rộng, thường 2–5. Ước tính hoặc đo bề rộng nhãn và giữ tối thiểu 8px giữa bounding boxes. Nhãn đầu/end dùng anchor phù hợp, không tràn plot.
9. Nếu chỉ đủ chỗ cho hai nhãn đầu/cuối thì chỉ hiện hai. Nếu thời gian bằng nhau hoặc một điểm, xử lý riêng; không chia cho 0, không vẽ đường giả qua nhiều điểm.
10. Bỏ/đánh dấu timestamp không hợp lệ có kiểm soát; không render Invalid Date, NaN hoặc Infinity.

#### C. Tương tác và dữ liệu

- Tooltip/crosshair theo pointer; đường bàn phím tương đương để đọc điểm hoặc bảng dữ liệu sẵn có. Không yêu cầu hover mới tiếp cận được giá trị.
- Điểm được chọn neo theo observed_at, không theo index đang dịch khi mẫu mới tới. Khi đổi host, clear điểm đã chọn.
- Nếu có Tạm dừng biểu đồ, chỉ đóng băng hiển thị chart/bảng tương ứng; không ngắt WebSocket và không dừng cập nhật toàn hệ thống.
- Host đang phân tích không tự đổi chỉ vì filter trạng thái hoặc metric mới thay đổi. Resolve host theo project scope; đổi dự án thì xử lý host không còn trong scope một cách tường minh.
- Không có host: empty state theo scope. Có host chưa có mẫu: nêu Chưa có mẫu telemetry, không vẽ đường 0%.
- Một mẫu: marker thật và timestamp, không có đường lịch sử giả. Số 0% hợp lệ vẫn hiển thị là 0%.
- RX/TX là counter tích lũy. Hiển thị dữ liệu một phần nếu một counter thiếu, không coi thiếu bằng 0 và không gắn /s.
- Mốc mới nhất lấy từ timestamp metric, không lấy heartbeat để tuyên bố metric vừa cập nhật.

### 5.4 Nhật ký sự kiện: vùng đọc log chuyên dụng

- Dùng biến thể full-page rõ ràng của component event stream; không phụ thuộc class cha không được render.
- Header gọn với count, input Lọc sự kiện hoặc hostname, nút Tạm dừng/Tiếp tục. Không lặp filter search có cùng tác dụng mà khác placeholder.
- V2 tổ chức full view như log workspace: toolbar điều khiển có trạng thái hiển thị, header cột nhẹ và vùng đọc liên tục; không thêm lớp card lồng. Cột timestamp khoảng 104px, event khoảng 160–180px, host khoảng 220–280px, nội dung chiếm phần còn lại khi đủ rộng; co/wrap theo breakpoint. Tránh cột host lấy quá nhiều chiều rộng đẩy nội dung sang xa.
- Desktop: dành phần chiều cao còn lại hợp lý cho log, flex/min-height: 0 khi dùng vùng cuộn nội bộ; table header sticky trong đúng vùng scroll. Tránh vừa page scroll dài vừa log cao 230px.
- Mobile: ưu tiên page scroll tự nhiên hoặc vùng log có chiều cao hữu dụng, không khóa người dùng trong scroll nhỏ. Event dài wrap; timestamp/type không che mô tả.
- Preview ở Tổng quan và full-page phải có giới hạn chiều cao độc lập. Không tăng max-height toàn component rồi làm preview một dòng bị phình.
- Event type là text/code nhỏ, màu tiết chế. metric_update thường trung tính hơn cảnh báo; không tô từng hàng bằng màu brand.
- Bảo toàn code gốc và mô tả. Không suy diễn metric_update là incident hoặc security alert.
- Tạm dừng chỉ đóng băng danh sách nhìn thấy; ingestion vẫn chạy. Nếu hiển thị số sự kiện mới đang chờ thì lấy từ buffer thật, không tự tăng giả.
- Đổi dự án/scope phải reset snapshot tạm dừng để không lẫn log dự án trước. Trạng thái pause sau đổi scope phải rõ, không âm thầm hiển thị dữ liệu cũ.
- Chỉ có buffer phiên hiện tại thì ghi rõ giới hạn đó; không gọi là toàn bộ lịch sử hệ thống hoặc cam kết log được lưu bền vững.
- Không tạo export/download hoặc API phân trang mới trong đợt tinh chỉnh này.

### 5.5 Modal chi tiết và thêm máy chủ

- Áp dụng cùng palette, radius và typography; header gọn, nội dung có nhóm, footer action rõ.
- Giữ focus trap, Escape, trả focus về trigger, body scroll lock và accessible title đã có; không viết lại nếu đang đúng.
- Chi tiết host: hostname/IP/project/status trước, metric và thời gian sau. Không lặp năm KPI fleet vào modal host.
- Thêm máy chủ: phân biệt nhập thông tin với kết quả/token enrollment. Primary action bám theo bước hiện tại, tránh hai nút primary cạnh tranh.
- Token/lệnh cài đặt chỉ copy khi người dùng bấm. Không tự chạy lệnh hoặc tạo máy chủ thật để kiểm thử hình thức.
- Giữ lỗi clipboard, retry và lỗi API. Error gắn với field khi xác định được, đồng thời có summary khi cần.
- Không thêm regex IP đơn giản làm hỏng IPv6; giữ backend làm nguồn validation chính cho format chưa có contract frontend rõ.

## 6. Tính đúng của dữ liệu và trạng thái — không đánh đổi cho hình thức

### 6.1 Phân biệt trạng thái wire và trạng thái hiển thị

Wire node.status hiện có các trạng thái unenrolled, online, offline, degraded. Không đổi enum wire để thêm một nhãn UI.

Nếu online nhưng thiếu mẫu hợp lệ, thêm trạng thái frontend Chưa có mẫu theo thứ tự ưu tiên:

1. unenrolled → Chờ đăng ký.
2. offline → Mất kết nối.
3. degraded hoặc bất kỳ metric hợp lệ vượt ngưỡng → Cần chú ý.
4. online nhưng thiếu CPU hoặc RAM hợp lệ → Chưa có mẫu.
5. online với đủ CPU/RAM hợp lệ và không vượt ngưỡng → Ổn định.

Ngưỡng hiển thị hiện tại: CPU > 75%, RAM > 85%; không tự đổi thành >=. Đây là ngưỡng trình bày, không phải backend detector hay incident. Nếu thêm nhóm Chưa có mẫu phải cập nhật đồng bộ tổng, legend, filter, aria label, style và test; không chỉ đổi một badge.

### 6.2 Quy tắc số liệu

- null/undefined/NaN không phải 0. Số 0 hợp lệ không phải missing.
- Giá trị thiếu hiển thị dấu —, không —%, NaN%, NaN MB hoặc Infinity.
- Trung bình chỉ lấy host có giá trị hợp lệ của metric tương ứng; hiển thị coverage để biết mẫu không đủ toàn cụm.
- RX/TX thiếu một phần phải được diễn đạt rõ. Tổng 0 B chỉ đúng khi các counter cần thiết thực sự có mẫu 0.
- Tỷ lệ sức khỏe luôn cho biết mẫu số là tổng host trong phạm vi hiện tại; không đổi mẫu số để tỷ lệ trông đẹp hơn.
- Filter ra 0 host khác với dự án trống. Không hiển thị trạng thái an toàn giả khi không có đối tượng đánh giá.

### 6.3 Timestamp, freshness và realtime

- observed_at: thời điểm metric được quan sát; last_seen: heartbeat của host; received_at: Controller nhận; timestamp envelope: thời điểm sự kiện. Không dùng thay thế nhau âm thầm.
- Nếu cần latestObservedAt ở view model, lấy từ mẫu thực REST/WS/demo nhất quán. Không sửa wire contract chỉ để hiển thị metadata.
- Giữ mergeSamples dedupe theo observed_at, sắp tăng dần và giới hạn history hiện có. Batch đến trễ hoặc đảo thứ tự không được ghi đè current value bằng mẫu cũ.
- Chọn latest từ lịch sử đã merge đúng thứ tự, không lấy incoming.at(-1) với giả định batch luôn sắp sẵn.
- Giữ requestId/historyRequestId/modeRef hoặc guard tương đương để response của dự án/host/chế độ cũ không ghi đè scope mới.
- Giữ partial success khi tải metric từng host; lỗi một host không làm mất dữ liệu mọi host.
- Chỉ hiển thị thời gian/tuổi của mẫu thật và trạng thái kết nối thật. Không đặt stale TTL 30/60 giây tùy ý nếu chưa có chính sách freshness xác định.
- Không sửa tự động chuyển demo/real hay cách dò Controller chỉ vì đang làm CSS.
- API backend có khả năng nhận start_time/end_time/limit; frontend hiện dùng giới hạn số mẫu và buffer. Không viết tài liệu sai rằng backend không hỗ trợ time range; cũng không mở rộng tính năng range query trong scope này.

### 6.4 Scope và selection

- Project là phạm vi chính. Xóa bộ lọc phụ không chuyển về Tất cả dự án.
- Search/header có tác dụng rõ với danh sách host. Khi chuyển Telemetry, không để search hoặc status filter tự thay host đang phân tích; host selector vẫn giới hạn theo project.
- Khi host không còn tồn tại trong project sau refresh, hiển thị trạng thái rõ hoặc chọn host thay thế theo quy tắc đã ghi trong UI; không giữ tên host cũ với chart host mới.
- Events luôn lọc theo project hiện tại; search event là filter trên dữ liệu đó, không kéo event của scope khác vào.
- Giữ tên route/hash hiện có để deep link không bị gãy. Không đổi router hoặc thêm routing dependency.

## 7. Bản đồ file và phạm vi chỉnh sửa

Đây là danh sách định hướng đã đối chiếu với cấu trúc hiện tại; không phải yêu cầu sửa tất cả file. Chỉ chạm file cần cho bước đang làm. Không refactor backend hoặc toàn bộ state architecture cho một thay đổi hình thức.

| File | Trách nhiệm trong đợt triển khai | Cần bảo toàn |
| --- | --- | --- |
| dashboard/src/index.css | Token màu, typography, reset/focus dùng chung | Thứ tự cascade với App.css; không bỏ focus toàn cục |
| dashboard/index.html | Nguồn font Be Vietnam Pro / IBM Plex Mono theo cơ chế hiện có | Font fallback, tiếng Việt, không thêm dependency |
| dashboard/src/App.css | Layout shell, panel, card, table, chart, breakpoint | Full-row Overview, search/project frame, responsive |
| dashboard/src/App.tsx | Page header/toolbar theo route, scope/selection/view state | Hash route, demo/real, luồng mở modal và dữ liệu |
| dashboard/src/components/Header.tsx | Project selector, search, trạng thái kết nối | Accessible labels, cấu hình Controller, refresh |
| dashboard/src/components/KPICards.tsx | Hierarchy KPI và coverage/missing values | Số liệu thật, card tách nhau, đơn vị |
| dashboard/src/components/InfrastructureOverview.tsx | Fleet health, project summary, ranking | Full-width từng section, phân biệt fleet/host |
| dashboard/src/components/AttentionPanel.tsx | Hàng host cần xử lý, lý do, ưu tiên | Không bịa incident; action vào đúng host |
| dashboard/src/components/NodeMatrix.tsx | Table/grid, sort, selected/hover, row action | Tính năng lưới, keyboard, stable selection |
| dashboard/src/components/TelemetryChart.tsx | Geometry, tick, legend, tooltip, data table | Số mẫu, timestamp, single point/missing data |
| dashboard/src/components/LiveEventStream.tsx | Biến thể preview/full, filter, pause, chiều cao | Scope và buffer thật, không mất ingestion |
| dashboard/src/components/NodeDetailModal.tsx | Phân nhóm thông tin host, nhịp chữ/spacing | Host identity và thao tác hiện có |
| dashboard/src/components/AddNodeModal.tsx | Form/enrollment result, lỗi, action hierarchy | Token, copy, retry; không tự thực thi lệnh |
| dashboard/src/components/Modal.tsx | Chỉ sửa nếu cần đồng bộ surface/focus | Focus trap, Escape, return focus, scroll lock |
| dashboard/src/presentation.ts | Health view model, format số và missing | Không nhầm domain/wire enum |
| dashboard/src/types.ts | Chỉ thêm kiểu frontend cần thiết | Wire contracts không đổi |
| dashboard/src/useInfrastructure.ts | Timestamp/merge/race guard nếu sửa lỗi đã nêu | REST/WS/demo, partial success, scope guards |
| dashboard/src/useWebSocket.ts | Ưu tiên không sửa | Vòng đời kết nối/reconnect và cleanup |
| dashboard/src/api.ts | Ưu tiên không sửa | Normalize URL, query, khả năng multi-host |
| dashboard/src/mockData.ts | Chỉ bổ sung fixture nếu thật sự cần | Không làm dữ liệu demo thành nguồn của real mode |
| dashboard/scripts/check-ui.mjs | Test render/behavior hiện có và regression phù hợp | Không xóa assertion chỉ để làm xanh |
| dashboard/scripts/check-dev.mjs | Kiểm chứng startup/module graph | Không coi HTML 200 là app đã chạy đúng |

Lưu ý cascade: index.css đang import App.css trước các rule global; rule xuất hiện sau có thể ghi đè component với cùng specificity. Xác định rule thắng trong computed style trước khi thêm selector. Không nối thêm nhiều block override trái nhau hoặc dùng !important hàng loạt.

## 8. Trình tự triển khai để model bám sát

### P0 — Baseline và giới hạn thay đổi

1. Đọc AGENTS.md, mục F10/F14 liên quan trong FOUNDATION_ROADMAP, tài liệu TECH_STACK và API_CONTRACTS theo routing của dự án. Đọc skill local trước thao tác UI.
2. Kiểm tra git status và branch. Không đụng thay đổi có sẵn ngoài scope. Tại thời điểm lập kế hoạch, pyproject.toml và uv.lock đang modified; đây không phải sản phẩm của kế hoạch UI.
3. Kiểm tra package.json, cấu trúc file liên quan, các script test. Đọc có chọn lọc, không quét toàn bộ backend hoặc master prompt dài không liên quan.
4. Chạy build/lint/test:ui để biết baseline nếu môi trường sẵn sàng. Ghi lỗi tồn tại trước khi sửa; không tự nhận lỗi cũ là do thay đổi mới.
5. Nếu có browser, mở các hash route hiện có và chụp baseline cùng viewport, zoom và bộ dữ liệu. Nếu browser không kết nối, ghi rõ giới hạn, không đứng chờ vô hạn.
6. Không dùng screenshots với demo data thay đổi ngẫu nhiên để khẳng định giá trị trước/sau phải giống nhau. Dùng fixture deterministic hoặc snapshot đã đóng băng khi so sánh layout.

Đầu ra P0: danh sách file dự kiến sửa, baseline test và khả năng kiểm tra browser. Không lập lại chiến lược thiết kế từ đầu.

### P1 — Tokens, shell và nhịp thị giác

File chính: index.css, App.css, App.tsx, Header.tsx.

1. Chuẩn hóa token V2 theo mục 3: thay palette/font được người dùng cho phép, giữ logo. Nâng nhịp chữ và độ phân lớp; không chỉ thay màu trong khi giữ toàn bộ cấu trúc đồng dạng.
2. Gọn sidebar identity và đếm trùng. Giữ navigation/keyboard/responsive.
3. Sửa hierarchy topbar/page header, loại breadcrumb thừa, action theo route.
4. Consolidate demo/connection labels; không thay logic kết nối.
5. Kiểm tra project border và search outer focus cả keyboard lẫn pointer.

Nghiệm thu: không mất ngữ cảnh dự án; không có hiệu ứng trang trí mới; nhìn rõ control; header các trang khác nhau theo nhiệm vụ. Sidebar không bị cắt menu ở zoom 200%.

### P2 — Tổng quan: ưu tiên chất lượng thị giác trước

File chính: KPICards.tsx, InfrastructureOverview.tsx, AttentionPanel.tsx, LiveEventStream.tsx ở biến thể preview, App.css.

1. Sửa KPI hierarchy, đơn vị, spacing, cảnh báo tiết chế; không sửa số liệu chỉ để demo đẹp.
2. Gọn sức khỏe toàn cụm và nhóm status; đưa link vào header.
3. Tổ chức hàng chú ý/ranking gần nhau và ổn định; bỏ footer/header trang trí thừa.
4. Preview event theo nội dung; project summary không phình khi chỉ có một dự án.
5. Chụp lại Tổng quan phần đầu và cuối. So với S1/S4/S5 về hierarchy, số lớp khung, vị trí thông tin cần xử lý; không chỉ kiểm tra màu token.

Nghiệm thu: metric card vẫn tách rời và bo tròn; mỗi section lớn full-width; ít chrome hơn nhưng chữ không nhỏ hơn; attention tiến gần đầu trang. Không yêu cầu mọi section cùng lọt một màn hình.

Sau P2 có checkpoint thị giác để tự đối chiếu kế hoạch. Không tự dừng chờ người dùng nếu không có lựa chọn mới vượt scope.

### P3 — Máy chủ và tính nhất quán selection

File chính: NodeMatrix.tsx, App.tsx, App.css, presentation.ts nếu cần.

1. Tinh chỉnh bảng/lưới, typography, badge, hover/selected và sort indicator.
2. Giữ view/sort trong phiên khi route hoặc modal thay đổi.
3. Bảo vệ selected host trước filter/realtime; reset filter không đổi project.
4. Kiểm tra zero result, hostname dài, IPv6, missing/0 CPU/RAM và hàng bằng nhau khi sort.

Nghiệm thu: liên kết/selection/status nhìn khác nhau; một thao tác bàn phím mở đúng host; hover không xóa selected; quay lại giữ chế độ bảng/lưới đã chọn.

### P4 — Telemetry và độ tin cậy biểu đồ

File chính: TelemetryChart.tsx, App.tsx, App.css; useInfrastructure.ts chỉ cho lỗi timestamp/merge liên quan.

1. Gộp ngữ cảnh host, bỏ chrome không liên quan; chart full-width thật.
2. Sửa hình học container/plot, font axis cố định, màu/line/fill theo mục 5.3.
3. Sửa tick theo miền thời gian và chống collision, đặc biệt dữ liệu dồn cuối trục như S6.
4. Sửa single/zero sample, invalid time, tooltip/data-table và selected point neo timestamp.
5. Nếu chạm realtime merge, thêm regression cho batch out-of-order, duplicate và response cũ. Không viết lại connection layer.
6. Kiểm tra host không tự đổi; số mẫu không bị ghi nhầm thành số phút; missing không biến thành 0.

Nghiệm thu: không trùng nhãn trục ở viewport nhỏ/lớn; text không phóng theo SVG; nhìn ra đường CPU/RAM ngay; không còn vùng màu phủ lấn dữ liệu; từng mẫu gắn đúng thời gian/host.

### P5 — Nhật ký, modal và polish liên trang

File chính: LiveEventStream.tsx, NodeDetailModal.tsx, AddNodeModal.tsx, App.css; Modal.tsx chỉ nếu cần.

1. Tách layout preview/full; nâng vùng đọc log thực, sticky header đúng scroll container.
2. Đồng bộ event typography, search/pause, empty/paused/scope-change states.
3. Đồng bộ modal surface/form/action và error readability, giữ accessibility đã có.
4. Rà soát tất cả route: border, focus, button heights, radius, count badge và duplicate source labels.

Nghiệm thu: một event preview không tạo khoảng trống lớn; full-page không bị bó trong max-height 230px; pause không ngắt ingestion; chuyển project không hiện snapshot cũ; modal không làm mất focus.

### P6 — Verification và bàn giao

1. Chạy lại các gate frontend; chạy quality gate dự án theo AGENTS khi môi trường hỗ trợ. Lỗi môi trường hoặc baseline phải được báo riêng, không tự sửa backend ngoài scope.
2. Kiểm tra browser ở bốn route, console/network/module errors, reload/deep link. App build được không chứng minh app render đúng.
3. Kiểm tra responsive/keyboard/contrast theo mục 9. Không tuyên bố đã thử những trường hợp chỉ đọc code.
4. Chụp trước/sau cùng viewport và dữ liệu; ghi đường dẫn artifact thực nếu có. Không bịa ảnh hoặc kết quả test.
5. Đọc diff, loại debug code/selector thừa và bảo đảm không chạm file người dùng ngoài scope.
6. Cập nhật bảng tiến độ cuối tài liệu bằng kết quả thực; không đánh dấu hoàn tất khi vẫn còn regression thuộc phạm vi.

## 9. Kiểm thử và tiêu chí nghiệm thu

### 9.1 Lệnh tham chiếu

Chạy từ repository root trong PowerShell; npm.cmd tránh vướng policy của npm.ps1. Trên hệ điều hành khác dùng npm tương ứng.

```powershell
npm.cmd --prefix dashboard run build
npm.cmd --prefix dashboard run lint
npm.cmd --prefix dashboard run test:ui
```

Kiểm tra dev server: dùng server đang chạy nếu đúng dự án. Chỉ khởi động mới khi cần; xác nhận cổng thực tế Vite báo, không coi 5174 là bắt buộc.

```powershell
npm.cmd --prefix dashboard run dev -- --port 5174
npm.cmd --prefix dashboard run test:dev -- http://localhost:5174
```

localhost ở đây chỉ là địa chỉ kiểm thử dev, không được hard-code vào logic Controller/Agent.

Quality gate dự án khi bàn giao triển khai:

```powershell
uv run ruff check src tests
uv run mypy src tests
uv run pytest -v
```

Chỉ chạy uv sync --all-extras khi thực sự cần thiết lập môi trường và đã kiểm tra tác động; không thay uv.lock/pyproject.toml để chữa vấn đề UI. Việc lập hai tài liệu Markdown này không yêu cầu chạy build hay toàn bộ Python suite.

### 9.2 Bảng tình huống bắt buộc

| Nhóm | Trường hợp | Kết quả yêu cầu |
| --- | --- | --- |
| Scope | Tất cả dự án / một dự án / filter ra 0 host | Đếm và dữ liệu cùng phạm vi; phân biệt empty với healthy |
| Reset | Project được chọn + search/status đang bật | Reset filter giữ project |
| Health | Offline, unenrolled, degraded, online thiếu mẫu | Không gắn thiếu mẫu thành ổn định; tổng các nhóm đúng |
| Threshold | CPU 75 / >75, RAM 85 / >85 | Đúng điều kiện > hiện tại, không thay đổi ngầm |
| Numeric | 0, null, undefined, NaN, counter thiếu một phía | 0 thật hiển thị; thiếu là —; không NaN/—% |
| Table | Sort tăng/giảm, giá trị bằng nhau, hover hàng selected | Icon/aria đúng; thứ tự ổn định; selected không biến mất |
| Navigation | Chuyển route, mở/đóng modal, back | Host/view/sort/scope giữ theo quy tắc |
| Chart | 0/1/2/120 mẫu | Empty, marker hoặc line đúng; không lỗi toán học |
| Time | Mẫu không đều, trùng, đảo thứ tự, dồn cuối miền thời gian | Không nhãn trùng; latest không bị lùi; dedupe đúng |
| Async | Đổi project/host/mode khi request cũ chưa xong | Response cũ không ghi đè scope mới |
| Connectivity | Demo, real disconnected, reconnect, partial fetch fail | Nhãn trung thực; không mất dữ liệu hợp lệ toàn cụm |
| Pause | Pause chart/log rồi có event mới, đổi project | Ingestion tiếp tục; snapshot không lẫn phạm vi |
| Enrollment | Validation/API/clipboard lỗi, đóng modal | Lỗi đọc được; không chạy lệnh; focus trở lại trigger |
| Long content | Hostname dài, tên project dài, IPv6, event message dài | Không chồng cột, không che action hoặc làm tràn trang |

### 9.3 Kiểm tra hình thức và accessibility

- Viewport tham chiếu theo CSS pixel: 390×844, 768×1024, 1366×768 và 1920×1080; thêm zoom 200% ở desktop.
- Không horizontal page overflow. Bảng rộng được cuộn trong vùng có chỉ dẫn nếu thật sự cần, không đẩy cả shell ra ngoài.
- Main navigation, project selector, search, filter, sort, row action, chart data access và modal dùng được bằng bàn phím.
- Focus ring hiện đúng khung bo góc, không bị overflow:hidden cắt mất. Không remove outline mà thiếu thay thế.
- Body text/label tiếng Việt không bị nhỏ hoặc clipped. Phân biệt label, value và metadata trong một lần nhìn.
- Không dùng màu làm dấu hiệu duy nhất. Kiểm tra cả badge text, dash/solid line, legend và aria.
- Tôn trọng prefers-reduced-motion; không tạo pulse liên tục chỉ để thể hiện realtime.
- Chart axis end labels không đè nhau tại mọi viewport được thử. Tooltip không ra ngoài màn hình; bảng dữ liệu đọc được khi không dùng chuột.
- Cả trạng thái hover và focus của selected row vẫn nhận diện được selection.
- Với ba host hoặc một event, không tạo vùng rỗng trong panel để ép tất cả section cùng chiều cao.
- Không chuyển console vận hành thành landing page; nền sáng V3 không phải quyền thêm hero/gradient/decorative illustration mới.

### 9.4 Giới hạn của test hiện có

- check-ui là kiểm tra render/SSR, không thay thế kiểm thử tương tác trình duyệt hoặc visual review.
- Nếu copy/markup thay đổi có chủ đích, cập nhật assertion tương ứng theo ý nghĩa. Không xóa kiểm tra route, active nav, demo labeling hoặc phân biệt Overview/Telemetry chỉ để test pass.
- Các assertion bám string HTML hoặc số tick cố định phải được thay bằng điều kiện ngữ nghĩa thích hợp; không giữ tám nhãn trục chỉ vì test cũ mong đợi tám.
- Tách Vite cache của script kiểm tra khi cần; không để kiểm tra SSR làm hỏng cache/module graph của dev server đang dùng.
- HTTP 200 cho index.html không đủ. Cần tải được JS modules, mount React và không có runtime exception/blank screen.
- Browser không khả dụng: vẫn hoàn thành phần kiểm tra tĩnh khả dụng, ghi NOT VERIFIED cho interaction/visual; không tuyên bố toàn bộ PASS và không chờ vô hạn.

## 10. Quy tắc thực thi tiết kiệm token và tránh lệch hướng

1. Xem mục 1–3 là ràng buộc chung; mỗi bước chỉ đọc lại phần trang và file liên quan. Không liên tục đọc lại toàn bộ repository hoặc lịch sử hội thoại.
2. Skill là công cụ kiểm chứng, không phải lý do đổi hướng đã duyệt. Search local theo typography/dashboard/chart/a11y và stack thật; không lặp khảo sát palette/template từ đầu.
3. Không cập nhật hoặc cài lại skill trong phiên triển khai UI nếu không có yêu cầu riêng; dùng bản local đang có. Nếu thiếu thì nêu rõ fallback.
4. Chia edit thành patch có thể kiểm tra được. Không gom toàn bộ App.tsx/CSS thành một lần viết lại lớn.
5. Ưu tiên tiến độ hữu hình: lưu patch/checkpoint sau từng phần, cập nhật ngắn. Không chỉ trả một câu hứa rồi phân tích kéo dài mà chưa tạo artifact.
6. Có vấn đề ngoài scope thì ghi nhận riêng; không làm backend/infra chỉ để đạt giao diện đẹp.
7. Không cần báo diễn giải suy nghĩ nội bộ; báo quyết định, file đã đổi, kết quả kiểm chứng và giới hạn thực tế.
8. Không ghi thành công cho công cụ chưa chạy. Không tự tạo commit/push/PR.

## 11. Tiến độ triển khai và nhật ký bàn giao

Đây là checkpoint lịch sử của **V1**. V2 tiếp tục từ code hiện có, không chạy lại P0–P6 như chưa có gì; đối chiếu mục 13 và diff thực. Các trạng thái DONE/PASS dưới đây không chứng nhận thiết kế V2 hoặc kết quả kiểm thử sau thay đổi V2.

| Bước | Trạng thái | Bằng chứng cần điền khi thực hiện |
| --- | --- | --- |
| P0 Baseline | DONE | feat/dashboard-observability-redesign; build/lint/14 UI checks pass trước sửa; giữ pyproject.toml và uv.lock có sẵn |
| P1 Shell/tokens | DONE | Sidebar/header gọn, toolbar theo route, focus outer search được kiểm tra trong Chromium |
| P2 Tổng quan | DONE | KPI tách rời, health phẳng, attention/ranking gần nhau; ảnh desktop/mobile đã kiểm tra |
| P3 Máy chủ | DONE | Sort direction, selected hover, view state trong App; browser kiểm tra view persistence và reset giữ project |
| P4 Telemetry | DONE | ResizeObserver, tick theo thời gian, marker mẫu đơn, merge mẫu đảo thứ tự; unit và browser tick spacing pass |
| P5 Nhật ký/modal | DONE | Preview theo nội dung, full log riêng; browser kiểm tra pause đổi scope, Escape và return focus |
| P6 Verification | DONE / giới hạn ghi dưới | Build/lint/18 UI checks, dev module graph, browser 16 route/viewport và Python gates; manual checks chưa làm được ghi NOT VERIFIED |

Khi bàn giao, dùng PASS / FAIL / NOT VERIFIED cho từng kiểm tra. FAIL phải có lỗi cụ thể; NOT VERIFIED phải có lý do. Bản build thành công không được thay cho mọi kiểm tra còn lại.

### Tiêu chí hoàn thành tổng thể

- [ ] Giữ toàn bộ lựa chọn thị giác người dùng đã duyệt, đặc biệt nền đen, bo góc, metric card tách và Overview full-row.
- [ ] Các vấn đề V01–V14 có thay đổi nhìn thấy được hoặc lý do không áp dụng rõ ràng, không chỉ refactor code.
- [ ] Tổng quan ưu tiên sức khỏe và việc cần xử lý; Telemetry ưu tiên host/time series; Nhật ký ưu tiên đọc event.
- [ ] Không có chart label overlap, missing-as-zero, host tự đổi hoặc dữ liệu khác project ghi đè.
- [ ] Không regression focus, selection, enrollment, REST/WS/demo hoặc multi-host config.
- [ ] Các gate chạy được đã pass; phần chưa chạy được được công khai, không giả chứng nhận hoàn tất.
- [ ] Không sửa file người dùng ngoài phạm vi, không tự commit/push, không triển khai milestone kế tiếp.

## 12. Nhật ký thực thi V1 ngày 23/10/2026 — bằng chứng lịch sử

Phần này giữ nguyên bằng chứng của lần tinh chỉnh đầu. Các mô tả font/palette giữ nguyên và trạng thái dev server là ghi nhận tại thời điểm V1; không phải ràng buộc hoặc xác nhận runtime hiện tại của V2. V2 phải có kiểm chứng riêng ở mục 13.

### 12.1 Milestone

Tinh chỉnh dashboard Foundation theo P0–P6. Đã triển khai frontend; không mở milestone mới. Checklist ở trên là tiêu chí tham chiếu ban đầu; bảng tiến độ và bằng chứng dưới đây là trạng thái thực thi hiện tại.

### 12.2 Scope

Đã chỉnh shell, Tổng quan, bảng/lưới máy chủ, Telemetry, Nhật ký và nhịp thị giác modal. Giữ React/Vite/TypeScript, logo, font, palette tối và layout Tổng quan full-row. Backend/wire contract không thay đổi.

### 12.3 Repository inspection

Branch đang làm: feat/dashboard-observability-redesign. Baseline frontend: build/lint và 14 UI smoke checks PASS. pyproject.toml và uv.lock đã có thay đổi trước phiên này và được bảo toàn. Không commit/push.

### 12.4 Files modified/created

| Nhóm file | Action | Trách nhiệm đã thực hiện |
| --- | --- | --- |
| dashboard/src/App.tsx, index.css, App.css | Modify | Shell gọn, route toolbar, tokens/typography, scope/selection, responsive và focus |
| components/Header.tsx, KPICards.tsx | Modify | Search Enter mở kết quả; trạng thái demo; KPI hierarchy, coverage, số 0/missing |
| components/InfrastructureOverview.tsx, AttentionPanel.tsx, HostMap.tsx | Modify | Health unknown nhất quán, status phẳng, ranking cap, attention ổn định |
| components/NodeMatrix.tsx | Modify | Sort icon, state bảng/lưới giữ ở App, metadata và số liệu dễ đọc |
| components/TelemetryChart.tsx | Modify | Plot theo width thực, trục thời gian không va nhãn, single point, keyboard/data table |
| components/LiveEventStream.tsx | Modify | Preview/full layout độc lập, buffer label và pause scope |
| components/NodeDetailModal.tsx, AddNodeModal.tsx | Modify | Copy tiếng Việt, hai bước enrollment, format metric thiếu |
| presentation.ts, useInfrastructure.ts | Modify | Frontend unknown/format an toàn; chọn latest sau merge thay vì cuối incoming batch |
| dashboard/src/telemetry.ts | Create | Helper merge/dedupe/time ticks dùng chung và kiểm thử được |
| dashboard/scripts/check-ui.mjs | Modify | Nâng từ 14 lên 18 checks; bổ sung ngưỡng, missing, zero, timestamp/order |
| dashboard/scripts/check-browser.mjs | Create | Chromium CDP smoke test không thêm dependency; ảnh và kiểm tra route/viewport/tương tác |

### 12.5 Architecture notes

Không sửa API hoặc enum node.status. unknown chỉ là health view model. Giữ guards REST/WS và partial-success hiện có. Helper telemetry tách riêng để chart và push handler dùng cùng quy tắc thời gian. Bảng host có controlled state từ App, đồng thời giữ fallback local state cho render độc lập/test.

### 12.6 Implementation và khác biệt nhìn thấy được

- V01–V03/V12/V14: bỏ breadcrumb phẳng, sidebar count/version trùng và footer nguồn; action theo route; header panel cùng nền; version chuyển vào trợ giúp.
- V04–V05/V13: KPI label sentence case, bỏ ONLINE/ATTENTION, icon trung tính, amber tint nhẹ, typography tăng ở host/section/metadata.
- V06–V08: sức khỏe dùng nhóm phẳng; link vào header; attention và ranking gom thông tin, track tối đa 640px; selected row xanh nhẹ, hover không ghi đè.
- V09–V10: bỏ host identity lặp và fill chart, dùng width container thực và clock ticks có khoảng cách; single sample có marker; không đổi số mẫu thành số phút.
- V11: event preview cao theo nội dung, full log có layout riêng; mobile dùng page scroll. Không tạo card giả để lấp khoảng trống.
- Trong kiểm tra 390px đã phát hiện sr-only ở header bảng nằm ngoài scroll container làm document tràn ngang. Đã đặt containing block cho table-scroll và kiểm tra lại cả 16 route/viewport đều PASS.

### 12.7 Commands và kết quả

- npm.cmd --prefix dashboard run build: PASS.
- npm.cmd --prefix dashboard run lint: PASS, không warning.
- npm.cmd --prefix dashboard run test:ui: PASS, 18 checks.
- npm.cmd --prefix dashboard run test:dev -- http://localhost:5174: PASS, 28 JS modules gồm React/React DOM.
- node dashboard/scripts/check-browser.mjs http://localhost:5174 http://127.0.0.1:9223: PASS trên Chromium headless test riêng. Cần khởi động Chromium với remote-debugging-port 9223 và user-data-dir riêng trước khi chạy; không dùng profile cá nhân.
- uv --no-cache run --frozen ruff check src tests: PASS.
- uv --no-cache run --frozen mypy src tests: PASS, 110 source files.
- uv --no-cache run --frozen pytest -v với basetemp/cache_dir trong vùng QA: 137 PASS, 3 cảnh báo deprecation từ Starlette/TestClient và tên HTTP 422 cũ. Không sửa backend để xử lý các cảnh báo ngoài scope UI.
- git diff --check -- dashboard: PASS.

### 12.8 Expected result và bằng chứng

Dev server đang chạy ở http://localhost:5174. Browser kiểm tra cả bốn hash route tại 390/768/1366/1920 CSS px: React mount, không page overflow, chart clock labels cách nhau ít nhất 8px, không runtime exception. Tương tác đã kiểm tra: giữ view khi chuyển route, host không đổi do search, reset giữ project, pause reset khi đổi project, modal Escape/return focus, outer search focus.

Ảnh sau triển khai: dashboard/node_modules/.cache/sentinelx-ui-qa/{overview,hosts,metrics,events}-{390,768,1366,1920}.png. Đây là artifact QA bị git ignore cùng node_modules, không phải asset sản phẩm. Ảnh full-page có thể vẽ bottom navigation tại vị trí viewport ban đầu giữa ảnh dài; đó là đặc điểm capture fixed element, không phải thanh nav nằm giữa nội dung khi cuộn thật.

### 12.9 Troubleshooting

- Kết nối Browser plugin timeout, nên dùng Chrome headless riêng; không kiểm tra hay truy cập profile cá nhân.
- Chrome CLI có giới hạn viewport nhỏ gây ảnh 390px bị crop sai: kết quả nghiệm thu cuối dùng Emulation.setDeviceMetricsOverride để kiểm tra CSS viewport thực.
- Cache uv mặc định lỗi quyền/đường dẫn; dùng --no-cache --frozen. Pytest basetemp/cache mặc định bị PermissionError; chuyển vào vùng QA riêng trong dashboard/node_modules/.cache, không sửa source/test Python.
- Dev server được để chạy để người dùng mở UI. Không có Controller thật được tạo mới hay lệnh enrollment tự thực thi trong QA.

### 12.10 Checkpoint và giới hạn nghiệm thu

PASS: code theo P1–P5, build/lint/SSR, browser 16 route/viewport, data formatting/order/ticks, project/reset/view/pause/modal/search focus, Ruff/mypy và 137 Python tests.

NOT VERIFIED: đối chiếu screenshot trước/sau với cùng dataset/thời điểm (không có baseline ảnh deterministic), zoom trình duyệt 200% thật, screen reader thực tế, đầy đủ ma trận lỗi API/clipboard/enrollment với Controller thật, mọi cặp contrast ở mọi state. Đã xem trực tiếp ảnh sau triển khai và không dùng ảnh để giả chứng minh các tương tác chưa kiểm tra.

Cảnh báo quality gate còn lại: 3 deprecation warnings có sẵn trong Python suite; không tuyên bố toàn repository đạt tiêu chí zero-warning. Không còn lỗi frontend thuộc các checks đã chạy.

### 12.11 Stop

Dừng ở phạm vi tinh chỉnh UI đã duyệt. Không triển khai M1–M8, không commit/push/PR. Các phần NOT VERIFIED là giới hạn nghiệm thu được ghi rõ, không được đổi thành PASS chỉ vì build thành công.

## 13. V2 — bản sắc công cụ vận hành, đã triển khai

Mục 13 giữ nguyên quyết định và bằng chứng lịch sử V2. Palette tối và focus cyan trong mục này đã được thay thế bởi V3 tại mục 3 và 14; typography, cấu trúc và hành vi V2 tiếp tục được giữ. PASS V2 không phải PASS V3.

### 13.1 Căn cứ và quyền thay đổi

Sau V1, người dùng gửi năm ảnh hiện tại và nhận xét giao diện mới chỉ gọn/đẹp hơn nhưng vẫn chung chung, giống UI sinh theo template. Người dùng cho phép chỉnh cả màu sắc, font family, font size và font weight để tối ưu trải nghiệm nền tảng giám sát. Đây là yêu cầu triển khai tiếp, không chỉ bổ sung kế hoạch.

V2 dùng định hướng **graphite operations workspace**: mạnh ở thứ bậc thông tin và tổ chức dữ liệu, tiết chế màu tương tác, chữ tiếng Việt dễ đọc. Không đồng nghĩa với giao diện terminal toàn monospace, dashboard neon/cybersecurity trang trí, hoặc website thương mại. Giữ logo, nền gần đen, bo góc, metric card độc lập cách nhau 16px và từng section Tổng quan full-row. Không sinh illustration, slogan, thành tích giả, sparkline giả hoặc số liệu mới để tạo cảm giác khác biệt.

### 13.2 Quyết định thị giác tại thời điểm V2

| Trục | Quyết định V2 | Dấu hiệu cần thấy khi so ảnh |
| --- | --- | --- |
| Màu | Canvas #0c1014, panel #141a20; action #91cedb; CPU #65d5bd, RAM #a7b6ff | Phân lớp graphite rõ vừa đủ, cyan chỉ đánh dấu thao tác/selection; không biến toàn trang thành xanh |
| Chữ | Be Vietnam Pro UI; IBM Plex Mono cho IP/time/code và số liệu bảng | Tiếng Việt đồng bộ; không còn các số KPI monospace mang tính trang trí |
| Cỡ/độ đậm | Body 15/400, label 14/500, metadata 13/400, H1 30/600, section 17/600, KPI 40/600 | Đọc được nội dung vận hành ở viewport desktop, không còn cảm giác chữ bé nằm trong khung rộng |
| KPI | Số sans-tabular làm tâm điểm; connectivity/attention có ngữ cảnh, CPU/RAM có marker ngưỡng thật, mạng tách đơn vị/RX/TX rõ | Năm card cùng hệ thống nhưng không phải năm bản sao icon–label–number vô nghĩa |
| Sức khỏe | Summary + distribution/status bên trong một section | Tỷ lệ và phân bố được đọc liền mạch, không chiếm nhiều hàng với khung con lặp |
| Cần chú ý | Cột host → nguyên nhân → trạng thái/action | Thấy ngay máy nào, vấn đề gì, thao tác nào; không gom mọi thứ ở nửa trái rồi để trống |
| Tải cao | Cột hostname → track có ngưỡng → giá trị → drill-down | So sánh hàng nhanh, giá trị sát track, không track siêu dài hoặc nửa panel rỗng |
| Inventory | Cột có tỷ lệ chủ đích, hostname/IP dễ đọc, metric cân đối | Selection và trạng thái khác nhau, dễ quét 5–50 hàng mà không phụ thuộc màu |
| Telemetry | Ngữ cảnh host gọn, readout CPU/RAM gần plot, trục/legend dễ đọc | Nhìn như công cụ phân tích một host, không lặp layout Tổng quan |
| Nhật ký | Toolbar điều khiển + vùng log; preview và full view khác nhau | Nội dung bắt đầu gần hostname, cột hợp lý, không hàng loạt wrapper/footer dư |

Các giá trị typography là mục tiêu desktop, không yêu cầu ép kích thước khiến mobile tràn. Đơn vị dài và hostname dài phải wrap/co có kiểm soát, không giảm toàn UI. Bố cục summary/distribution hai vùng **bên trong** cùng panel không vi phạm yêu cầu mỗi section lớn toàn hàng.

### 13.3 Thứ tự triển khai V2

1. Cập nhật tài liệu này và prompt để loại bỏ khóa font/palette cũ; giữ toàn bộ guardrails dữ liệu và bằng chứng V1.
2. Đổi font source, token, type scale, shell và selected/focus states. Giữ khung project/search, không tạo hành vi mới không có backend.
3. Sửa markup/CSS KPI và Overview theo bố cục riêng của từng loại dữ liệu. Không dùng một loạt override để phủ lên CSS cũ; chỉnh rule gốc khi có thể.
4. Áp hệ chữ/nhịp màu mới nhất quán cho inventory, telemetry, events và modal; tổ chức cột/controls theo nhiệm vụ.
5. Chạy lại build/lint/UI/dev/browser kiểm tra phần bị tác động. Xem ảnh trực tiếp cả desktop và mobile; không coi đổi token hay build thành công là đủ chứng minh thay đổi thị giác.
6. Ghi bằng chứng V2 riêng, giữ nguyên các mục NOT VERIFIED chưa được kiểm tra. Không tạo commit/push hoặc mở rộng milestone.

### 13.4 Checkpoint V2

| Bước | Trạng thái | Bằng chứng / phần còn lại |
| --- | --- | --- |
| V2-A Đặc tả và prompt | UPDATED | Đã ghi quyền thay font/palette từ phản hồi mới, token/type scale, bố cục riêng và tiêu chí kiểm chứng |
| V2-B Font/token/shell | IMPLEMENTED / CHECKED | Font availability ui/mono đều true trong Chromium; sans KPI, token graphite/cyan, type scale và shell đã render |
| V2-C Overview/Inventory/Telemetry/Events | IMPLEMENTED / CHECKED | Health 2 vùng trong 1 section; attention/ranking có cột; inventory/telemetry/events có bố cục riêng; đã xem ảnh desktop/mobile |
| V2-D Verification | PASS với giới hạn | Kết quả lượt V2 và các phần NOT VERIFIED tại 13.6; không dùng PASS V1 thay kiểm tra mới |

### 13.5 Tiêu chí nghiệm thu thị giác V2

- [ ] Ảnh desktop cùng viewport thấy thay đổi ở **cả** typography, surface/interaction color và cấu trúc ít nhất health/attention/ranking; không chỉ màu nền hoặc border.
- [x] Màu không cạnh tranh với cảnh báo; CPU/RAM nhất quán, ngưỡng thật, không thêm trend hoặc dữ liệu giả.
- [x] Năm KPI vẫn độc lập, gap 16px; các section lớn vẫn toàn hàng, giữ logo và nền gần đen.
- [x] Attention/ranking không còn cụm nội dung bị cap ở nửa trái màn hình; cột liên kết thông tin gần nhau, mobile không tràn.
- [x] H1/section/body/label/metadata có thứ bậc đọc được; số KPI sans-tabular; mono chỉ dành cho dữ liệu kỹ thuật có chọn lọc.
- [x] Bảng máy chủ, chart và log có bố cục sát công việc riêng, không nhân bản cùng mẫu card/header/footer.
- [ ] Check cả bốn route ở 390/768/1366/1920 CSS px, focus/keyboard, selected state, modal, hostname dài và chart tick collisions; zoom/screen reader/Controller thật chưa kiểm tra phải ghi rõ.
- [x] Build/lint/UI/dev/browser chạy sau V2 có kết quả được ghi riêng; không lặp lại PASS lịch sử V1 như thể vừa chạy.

Không thể chứng nhận khách quan rằng một UI “không AI”. Tiêu chí ở đây là các khác biệt cụ thể, có lý do sử dụng và quan sát được; người dùng vẫn là người quyết định cảm nhận thẩm mỹ cuối cùng.

### 13.6 Bàn giao triển khai V2

1. **Milestone:** Refinement frontend Foundation F10–F14; không bắt đầu M1–M8.
2. **Scope:** Typography, palette, shell, KPI, bố cục Overview/Hosts/Telemetry/Events, biểu tượng drill-down và QA. Không đổi backend/API/database/dependency; giữ thay đổi có sẵn trong pyproject.toml và uv.lock.
3. **Repository inspection:** Đối chiếu các component hiện tại, CSS cascade, index.html, script UI/browser và năm ảnh người dùng. UI UX Pro Max được áp dụng có chọn lọc; loại gợi ý landing page/glassmorphism vì sai bối cảnh.
4. **Files:** V2 sửa dashboard/index.html (nguồn font/theme), src/index.css (token/primary button), src/App.css (type/layout), App.tsx và components/{KPICards,InfrastructureOverview,AttentionPanel,NodeMatrix,TelemetryChart,LiveEventStream,HostMap}.tsx (composition/internal chevron), scripts/check-browser.mjs (assertions V2), hai tài liệu gốc. Các thay đổi V1 trước đó giữ nguyên.
5. **Architecture:** Chỉ frontend; giữ REST/WS, multi-host config, dữ liệu thật/mô phỏng và wire contract. Tỷ lệ ổn định không được gọi là uptime/SLA; vạch tài nguyên dùng đúng ngưỡng 75/85.
6. **Implementation:** Đã lưu code, không phải mockup. KPI lớn dùng sans-tabular; CPU/RAM có marker; health summary/distribution cùng section; attention host/IP → status/reason → Kiểm tra; ranking host/track/value; inventory đọc ngang; chart readout CPU/RAM lớn; log trung tính, warning có dấu cạnh. Đổi mũi tên mở ngoài thành chevron cho drill-down nội bộ. Chart khi mẫu hover hết buffer không còn hiển thị timestamp cũ với giá trị mới.
7. **Commands/gates lượt V2:** build PASS; lint PASS; test:ui 18 PASS; test:dev 28 JS module PASS; check-browser 16 route/viewport PASS và không Runtime exception. Ruff PASS; mypy 110 source files PASS; pytest 137 PASS với 3 deprecation warnings có sẵn. Chạy uv --no-cache run --frozen; pytest dùng basetemp/cache QA như mục 12.9.
8. **Expected result/evidence:** Mở http://localhost:5174. Ảnh QA trong dashboard/node_modules/.cache/sentinelx-ui-qa, cùng mẫu tên tại 12.8. Đã xem Overview desktop/mobile/tablet, Hosts, Telemetry, Events. Browser kiểm tra gap KPI 16, font KPI sans, marker 75/85, section một cột, health desktop chia vùng/mobile xếp dọc, chart tick không chồng, scope/view/pause/modal/search-focus. Font availability Be Vietnam Pro và IBM Plex Mono đều true trong lần chạy.
9. **Troubleshooting:** Port5174 đã có server, dùng lại chứ không dừng tiến trình người dùng. Font Google Fonts dùng display=swap và fallback hệ thống; không khẳng định offline vẫn tải được webfont. Bảng rộng cuộn trong vùng bảng trên mobile, không đẩy tràn document.
10. **Checkpoint:** PASS các gate nêu trên; primary/secondary/muted trên panel lần lượt 15.54/11.06/7.75:1, action10.06:1, text trên primary button9.49:1, viền control trên canvas3.99:1, CPU/RAM trên panel9.85/8.99:1 (tính từ token sRGB). Đây không phải audit WCAG toàn bộ. NOT VERIFIED: pixel-diff trước/sau cùng dữ liệu/thời điểm, zoom trình duyệt200% thật, screen reader, toàn bộ trạng thái contrast/modal, ma trận lỗi với Controller thật. Chưa được người dùng nghiệm thu thẩm mỹ.
11. **Stop:** Dừng đúng scope V2; không commit/push/PR, không mở milestone tiếp theo. Các giới hạn kiểm chứng được giữ rõ, không gọi toàn bộ accessibility/backend flow đã nghiệm thu.

## 14. V3 — nền sáng trung tính, focus graphite

### 14.1 Quyền thay đổi và phạm vi

Người dùng đã chấp thuận chuyển sang palette trắng–graphite sau khi xem V2. Đây là yêu cầu triển khai frontend, không chỉ đề xuất. V3 thay màu canvas/panel/text/control/status/chart, màu selected/hover và focus. Giữ font Be Vietnam Pro / IBM Plex Mono, type scale, bố cục các trang, logo, card radius 18px, control radius 10px, modal radius 24px, gap KPI 16px và section 24px.

Không đổi dữ liệu/REST/WebSocket, selection/scope, demo, enrollment, modal keyboard hoặc backend. Không thêm dependency, theme toggle hoặc cơ chế lưu theme khi chưa được yêu cầu. V1/V2 là lịch sử, không khôi phục palette tối vì prompt cũ.

### 14.2 Hạng mục thực thi

1. Chuyển semantic tokens theo mục 3.1 và color-scheme/theme-color sang light; không dùng filter đảo màu.
2. Primary CTA graphite với chữ trắng; link xanh riêng, status/chart tối hơn để đọc trên nền trắng. Selection nhẹ và không lẫn với trạng thái sức khỏe.
3. Focus trung tính #4b5563, 2px, outline-offset 0, sát khung bo; composite search chỉ có một viền trên wrapper. Không bỏ keyboard focus.
4. Loại màu tối hardcoded trong nav active, host selected/grid, scrollbar, selection highlight, modal scrim/shadow. Giữ logo và nguồn font.
5. Kiểm tra cả Overview, Hosts, Telemetry, Events và modal; ánh xạ màu mới không được làm mất axis/legend/status, làm chữ quá nhạt hoặc tạo overflow.
6. Cập nhật test theo thiết kế focus có chủ đích, bảo toàn assertions hành vi; ghi bằng chứng V3 riêng sau khi chạy.

### 14.3 Checkpoint V3

| Bước | Trạng thái | Bằng chứng / phần còn lại |
| --- | --- | --- |
| V3-A Đặc tả / prompt | UPDATED | Đã cập nhật yêu cầu nền sáng, token chính xác và thay thế khóa nền đen của hướng dẫn hiện hành; giữ lịch sử V1/V2 |
| V3-B Tokens / focus / states | IMPLEMENTED / CHECKED | Palette light, graphite CTA/focus, neutral selected/nav/grid/skip-link; đã kiểm tra màu tính toán và ảnh render |
| V3-C Build / lint / UI / dev | PASS | Build và lint PASS; test:ui 18 PASS; test:dev 28 JS module PASS trong lượt V3 |
| V3-D Browser / visual / contrast | PASS trong phạm vi kiểm tra | 16 tổ hợp route/viewport PASS, không runtime exception; focus/search/modal PASS; 13 cặp contrast token và chữ trắng trên primary button PASS; giới hạn tại 14.5 |

### 14.4 Tiêu chí bàn giao

- Nền #f5f6f7 và panel trắng thống nhất toàn nền tảng; không còn mảng selected/sidebar tối ngoài ý muốn.
- Primary button graphite, link xanh tiết chế; chart CPU/RAM và badge trạng thái đọc được trên nền sáng, không dùng màu làm dấu hiệu duy nhất.
- Focus gọn theo khung, không glow/neon, vẫn thấy rõ khi điều hướng bàn phím; search không có hai outline.
- Font/type scale/layout/card spacing và các hành vi V2 không đổi; không backend/dependency/commit/push/PR.
- Báo build/lint/UI/dev/browser/contrast đúng kết quả thực. Kiểm chứng chưa chạy ghi NOT VERIFIED; screen reader, zoom 200% thật và Controller thật chưa kiểm tra không được gọi PASS.

Trạng thái bàn giao hiện tại: **Đã triển khai V3; các kiểm tra đã chạy PASS. Giới hạn nghiệm thu còn lại được ghi rõ dưới đây, không chứng nhận WCAG toàn bộ hoặc Controller thật.**

### 14.5 Bàn giao triển khai V3

1. **Milestone:** Tinh chỉnh frontend trên Foundation F10–F14, không triển khai M1–M8.
2. **Scope:** Chuyển palette tối sang trắng–graphite và chỉnh focus/interaction colors. Giữ logo, font/type scale, cấu trúc từng trang, radius/gap và logic dữ liệu V2; không thêm theme toggle/dependency/backend.
3. **Repository inspection:** Đối chiếu semantic tokens, các màu hardcoded trong CSS, chart SVG, theme-color và assertions browser. Dùng UI UX Pro Max để rà contrast/focus phù hợp web, không áp template marketing.
4. **Files:** dashboard/src/index.css (palette, CTA, focus, scrim/shadow), dashboard/src/App.css (surface/selected/search focus), dashboard/index.html (theme-color), dashboard/scripts/check-browser.mjs (kiểm chứng V3), hai tài liệu gốc. Giữ nguyên mọi thay đổi không liên quan của người dùng.
5. **Architecture:** REST/WebSocket, wire contracts, Controller URL cấu hình, session state, enrollment và luồng demo giữ nguyên. Không thay dữ liệu hoặc làm giả trend vì đổi theme.
6. **Implementation:** Canvas #f5f6f7/panel trắng; graphite CTA/focus; link xanh tiết chế; CPU/RAM và status đậm hơn trên nền sáng. Neutral hóa nav active, host row/tile selected và skip-link; bỏ vòng cyan tách lớp, search chỉ focus khung ngoài. Không xóa keyboard focus.
7. **Commands/gates lượt V3:** npm.cmd --prefix dashboard run build PASS; run lint PASS; run test:ui 18 PASS; run test:dev -- http://localhost:5174 kiểm tra 28 JS module PASS. Script check-browser chạy 16 tổ hợp bốn route × bốn viewport PASS, không runtime exception. Ruff PASS; mypy 110 source files PASS; pytest 137 PASS, còn 3 deprecation warnings có sẵn. Các lệnh Python dùng uv --no-cache run --frozen và pytest basetemp/cache QA như mục 12.9.
8. **Expected result/evidence:** Bản hiện tại tại http://localhost:5174. Ảnh mới trong dashboard/node_modules/.cache/sentinelx-ui-qa: light-{route}-{width}.png, light-search-focus.png và light-add-host-modal.png. Agent chính đã xem Overview 1920, Telemetry 1366, Events 390, search focus và modal; đây là ảnh sau V3, không dùng ảnh V2 để chứng nhận theme mới.
9. **Troubleshooting:** Không dừng dev server có sẵn. Nếu trình duyệt còn CSS cũ, tải lại trang và xác nhận đúng port. Giữ 3 cảnh báo Python có sẵn; không sửa backend ngoài scope hoặc tuyên bố zero-warning toàn repository. Font network/fallback như V2.
10. **Checkpoint:** PASS các gate trên. Focus ngoài search đo được outline 2px, rgb(75, 85, 99), offset 0; input outline none. Modal Escape và return-focus PASS. Đo 13 cặp token cùng chữ trắng trên primary button: primary/secondary trên panel 16.10/7.41:1, muted trên canvas 5.07:1, CPU/RAM 4.99/5.86:1, focus 7.56:1, các cặp status được kiểm tra ít nhất 4.77:1. Đây là đo cặp màu sRGB và kiểm tra hành vi có phạm vi, không audit WCAG toàn bộ. NOT VERIFIED: screen reader thực tế, zoom trình duyệt 200% thật, toàn bộ luồng/lỗi với Controller thật, toàn bộ cặp màu/trạng thái và pixel-diff trước/sau cùng thời điểm. Cảm nhận thẩm mỹ cuối cùng vẫn chờ người dùng đánh giá.
11. **Stop:** Dừng đúng phạm vi light theme V3; chưa commit/push/PR, không mở rộng milestone. Không dùng kết quả PASS trong phạm vi này để tuyên bố mọi accessibility/live-data flow đã được nghiệm thu.

## 15. V4 — Phân cấp vận hành và ý nghĩa dữ liệu

### 15.1 Quyết định đã duyệt và triển khai

- Giữ palette V3, Be Vietnam Pro/IBM Plex Mono, logo và dữ liệu thực; không thêm thư viện, backend, theme switch hoặc milestone.
- “Cần xử lý” = cảnh báo + mất kết nối + chờ đăng ký. Nếu chỉ chờ đăng ký, KPI/project count trung tính, không vàng cảnh báo. Nhóm warn gọi “Cảnh báo”. Nhãn từng host phân biệt “Vượt ngưỡng” khi CPU >75% hoặc RAM >85%; degraded dưới ngưỡng là “Suy giảm”. Không đổi classifier/domain status.
- “Tỷ lệ máy chủ ổn định” vẫn = số ổn định / toàn bộ host trong phạm vi, gồm pending. Không đổi mẫu số, không gọi SLA/health score. Ranking đổi thành “Máy chủ sử dụng tài nguyên nhiều nhất”, vẫn top5 mẫu hợp lệ, không giả tất cả đều quá tải.
- H1 desktop 28px/600; giữ body15, section17, KPI40 và mobile thích nghi. KPI padding16/18, min-height148; tiêu đề bảng/preview gọn hơn, ranking min-height64. Giữ gap KPI16, các section full hàng. Số trong bảng/hostname log tăng lên màu chữ chính; IP/time/code vẫn phụ.
- Lọc trạng thái cạnh metadata phạm vi thay vì chiếm riêng một hàng. Topbar hiển thị nguồn mô phỏng/kết nối và action kết nối; bỏ banner demo lặp phía dưới. Mobile vẫn luôn thấy nguồn, không giấu trạng thái demo.
- Chart: readout lớn luôn là mẫu mới nhất; tooltip lịch sử theo vị trí X, đo kích thước và clamp hai mép; giữ keyboard Home/End/mũi tên/Escape và thông báo mẫu đang xem. CPU solid/RAM dashed, trục0–100, sample count không đổi thành phút. Không làm giả độ dao động.
- Events: lọc Tất cả / Trạng thái & cảnh báo / Telemetry, mặc định Tất cả. Giữ event chưa biết trong Tất cả. Tìm kiếm cả nhãn dễ đọc, raw code, host và payload; kết hợp category. Giữ mã sự kiện dưới nhãn. Trạng thái cập nhật/tạm dừng ngay cạnh controls; pause giữ snapshot, không dừng ingestion; đổi scope reset như trước.
- Trang Events dùng cuộn trang duy nhất, không max-height/scroll lồng cho danh sách. Controls/tên cột cùng wrapper sticky; viewport cao <=600px bỏ sticky để tránh che vùng đọc. Mobile controls wrap, search và pause cùng hàng, bộ lọc không tràn.

### 15.2 Files và ranh giới

| File | Trách nhiệm V4 |
| --- | --- |
| dashboard/src/App.tsx, components/Header.tsx | Gọn header/scope; một vị trí nguồn dữ liệu |
| dashboard/src/App.css | Hierarchy/density, event single scroll/sticky, tooltip/mobile |
| dashboard/src/presentation.ts | Nhãn cảnh báo chính xác; không đổi nodeHealth |
| components/KPICards.tsx, AttentionPanel.tsx, InfrastructureOverview.tsx, NodeMatrix.tsx | Áp dụng semantics và nhãn theo từng khối |
| components/TelemetryChart.tsx | Latest readout tách historical tooltip, keyboard feedback |
| dashboard/src/events.ts (mới), components/LiveEventStream.tsx | Pure filtering/labels, controls và pause snapshot |
| dashboard/scripts/check-ui.mjs, check-browser.mjs | Regression cho V4, giữ assertions cũ |
| Hai tài liệu gốc | Ghi quyết định và checkpoint hiện hành |

Đường dẫn components ở bảng thuộc dashboard/src/. Giữ nguyên thay đổi có sẵn trong backend, pyproject.toml, uv.lock. Không commit/push/PR; branch làm việc feat/dashboard-observability-redesign.

### 15.3 Kiểm chứng phải giữ khi chỉnh tiếp

- Pending-only: count Cần xử lý vẫn1 nhưng không stat-attention. Offline/threshold warning vẫn nhấn màu. Degraded dưới ngưỡng không ghi Vượt ngưỡng.
- Label tỷ lệ nói đúng mẫu số; ranking không đổi filter/sort chỉ để tạo dữ liệu đẹp.
- Tất cả giữ unknown event; category + search giao nhau, không đổi thứ tự/mutate input. Pause rồi đổi filter và quay lại All giữ snapshot.
- Home/End xem lịch sử không đổi readout mới nhất; tooltip không vượt vùng chart; x tick không đè. Trục luôn0–100.
- Demo source nhìn thấy cả bốn breakpoint; search một focus ring, modal Escape/return-focus; không document overflow, full-row Overview.

### 15.4 Checkpoint bàn giao — 23/10/2026

**Code đã hoàn thành; các gate dưới đây PASS. Không đồng nghĩa đã nghiệm thu toàn bộ accessibility hoặc Controller thật.**

| Kiểm tra | Kết quả lượt V4 |
| --- | --- |
| npm.cmd --prefix dashboard run build | PASS, chạy lại sau CSS cuối |
| npm.cmd --prefix dashboard run lint | PASS, không warning |
| npm.cmd --prefix dashboard run test:ui | 23 PASS; baseline trước lượt này18 PASS |
| npm.cmd --prefix dashboard run test:dev -- http://localhost:5174 | 29 JS module PASS |
| node dashboard/scripts/check-browser.mjs http://localhost:5174 http://127.0.0.1:9223 | 16 tổ hợp4 route ×390/768/1366/1920 PASS; không runtime exception |
| Browser V4 assertions | Source visible, All/default/group filters, pause snapshot, overflowY visible/sticky style, latest readout vs latest table row, tooltip Home/End trong bounds PASS |
| Browser regression | Giữ host/view, reset giữ project, pause reset khi đổi scope, search focus, modal Escape/return-focus PASS |
| Contrast token | 13 cặp và chữ trắng trên primaryCTA PASS; không chứng nhận mọi state WCAG |
| uv --no-cache run --frozen ruff check src tests | PASS |
| uv --no-cache run --frozen mypy src tests | PASS110 files |
| uv --no-cache run --frozen pytest -v | 137 PASS, 3 cảnh báo Starlette deprecation có sẵn; dùng basetemp QA duy nhất và cache trong node_modules/.cache |
| git -c core.safecrlf=false diff --check -- dashboard | PASS |

Browser tích hợp timeout; Chromium headless dùng profile QA riêng trong workspace, phải chạy ngoài sandbox vì GPU/access denied trong sandbox. Không dùng profile cá nhân. Script QA seed random và dừng interval chỉ trong trang kiểm thử để oldest sample không bị sliding window loại giữa kiểm tra Home/End; không sửa timer ứng dụng. Vì vậy không coi đây là chứng nhận realtime ingestion dài hạn.

Ảnh sau V4: dashboard/node_modules/.cache/sentinelx-ui-qa/v4-light-{route}-{width}.png; thêm ảnh focus/modal cùng prefix. Main đã xem Overview1920/390, Hosts768, Telemetry1366, Events1366/390. Full-page capture có thể đặt fixed bottom navigation giữa ảnh dài; không dùng ảnh này để kết luận clipping ngoài viewport. Không có pixel-diff trước/sau cùng thời điểm.

NOT VERIFIED: screen reader thực tế, browser zoom200% thật, toàn ma trận Controller/enrollment/error thật, toàn bộ focus khi sticky/zoom, tất cả cặp màu/state, stress realtime. Bảng rộng ở tablet giữ cuộn ngang nội bộ, không tràn document. Chờ người dùng đánh giá thẩm mỹ.

Điểm dừng: hoàn thành V4, không mở milestone tiếp theo, không tự làm lại P0–P6/V1–V3. Dev server có sẵn giữ chạy. Không commit/push.
