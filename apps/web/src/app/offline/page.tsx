export const metadata = { title: "Không có kết nối — Campus 24/7" };

/** Shown by the service worker when a page cannot be loaded. Static on purpose: it must work with no network and holds no personal data. */
export default function OfflinePage() {
  return (
    <main className="mx-auto flex min-h-[60vh] max-w-md flex-col items-center justify-center gap-4 p-6 text-center">
      <h1 className="text-xl font-semibold">Bạn đang ngoại tuyến</h1>
      <p className="text-sm">Không kết nối được tới Campus 24/7. Hãy kiểm tra mạng rồi thử lại. Nội dung cá nhân không được lưu trên thiết bị khi ngoại tuyến.</p>
      <a href="/" className="inline-flex min-h-[44px] items-center rounded-lg border px-5 text-sm font-medium">Thử lại</a>
    </main>
  );
}
