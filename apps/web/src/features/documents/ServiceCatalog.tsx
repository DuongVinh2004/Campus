"use client";

import { useState } from "react";
import Link from "next/link";
import { BadgeCheck, BookOpen, Headphones, Search, ArrowRight, History, HelpCircle } from "lucide-react";
import type { ServiceKind } from "../../lib/data/api/service-gateway";

const services = [
  { key: "certificate", title: "Giấy xác nhận sinh viên đang học", category: "Cấp giấy xác nhận", description: "Chuẩn bị giấy xác nhận theo mục đích và đơn vị tiếp nhận của bạn.", icon: BadgeCheck },
  { key: "GRADE_APPEAL", title: "Phúc khảo kết quả học tập", category: "Đào tạo & Khảo thí", description: "Đối chiếu học phần, điều kiện và gửi yêu cầu phúc khảo theo hướng dẫn.", icon: BookOpen },
  { key: "GENERAL_SUPPORT", title: "Hỗ trợ thủ tục học vụ", category: "Hỗ trợ sinh viên", description: "Gửi câu hỏi hoặc vấn đề cần cán bộ hỗ trợ và theo dõi phản hồi.", icon: Headphones },
] as const;

export function ServiceCatalog({ onChoose, onHistory, authenticated, onCertificate, preparationOnly = false }: { onChoose: (kind: ServiceKind) => void; onHistory: () => void; authenticated: boolean; onCertificate?: () => void; preparationOnly?: boolean }) {
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("Tất cả");
  const categories = ["Tất cả", ...new Set(services.map(item => item.category))];
  const visible = services.filter(item => (category === "Tất cả" || item.category === category) && `${item.title} ${item.category}`.toLocaleLowerCase("vi").includes(query.toLocaleLowerCase("vi")));
  return <div className="campus-service-catalog space-y-6">
    <section className="campus-catalog-intro"><span className="campus-catalog-icon"><BadgeCheck size={24} /></span><div><h2>Dịch vụ một cửa sinh viên</h2><p>{preparationOnly ? "Chọn thủ tục để chuẩn bị và lưu nháp. Tiếp nhận chính thức chưa được kết nối." : "Thực hiện thủ tục học vụ trực tuyến. Kiểm tra thông tin và xem trước trước khi xác nhận gửi."}</p></div></section>
    <div className="campus-catalog-tools"><label className="campus-catalog-search"><Search size={18} /><input value={query} onChange={event => setQuery(event.target.value)} placeholder="Lọc nhanh theo tên thủ tục, mã dịch vụ…" aria-label="Tìm dịch vụ" /></label><div>{authenticated ? <button type="button" className="fluent-btn-secondary" onClick={onHistory}><History size={16} />Lịch sử yêu cầu</button> : <Link href="/login?redirect=%2Ftickets" className="fluent-btn-secondary"><History size={16} />Lịch sử yêu cầu</Link>}<Link href="/chat" className="fluent-btn-secondary"><HelpCircle size={16} />Hướng dẫn thủ tục</Link></div></div>
    <div className="campus-filter-chips" role="group" aria-label="Nhóm dịch vụ">{categories.map(value => <button key={value} type="button" aria-pressed={category === value} onClick={() => setCategory(value)}>{value}<span>{value === "Tất cả" ? services.length : services.filter(item => item.category === value).length}</span></button>)}</div>
    <div className="campus-catalog-grid">{visible.map(item => <article key={item.key} className="campus-catalog-card"><div className="campus-catalog-card-top"><span><item.icon size={23} /></span><small>{item.category}</small></div><h3>{item.title}</h3><p>{preparationOnly ? item.key === "GRADE_APPEAL" ? "Chuẩn bị nội dung cần hỏi về phúc khảo; điều kiện và hạn nộp chưa được xác minh." : item.key === "GENERAL_SUPPORT" ? "Soạn vấn đề cần hỗ trợ và lưu nháp để đọc lại." : item.description : item.description}</p><footer><span>Đối chiếu hướng dẫn và nguồn tại biểu mẫu</span>{!authenticated ? <Link href="/login" className="fluent-btn-primary">Đăng nhập để tiếp tục<ArrowRight size={16} /></Link> : item.key === "certificate" && !onCertificate ? <Link href="/tickets?new=1" className="fluent-btn-primary">Tạo yêu cầu<ArrowRight size={16} /></Link> : <button type="button" className="fluent-btn-primary" onClick={() => item.key === "certificate" ? onCertificate?.() : onChoose(item.key as ServiceKind)}>{preparationOnly ? "Chuẩn bị nháp" : "Tạo yêu cầu"}<ArrowRight size={16} /></button>}</footer></article>)}</div>
    {!visible.length && <div className="campus-panel text-center" role="status">Không tìm thấy dịch vụ phù hợp. Hãy thử từ khóa khác.</div>}
    <aside className="campus-catalog-help"><HelpCircle size={24} /><div><strong>Bạn chưa tìm thấy thủ tục cần thực hiện?</strong><p>Trợ lý học vụ giúp bạn tìm hướng dẫn và căn cứ phù hợp.</p></div><Link href="/chat" className="fluent-btn-secondary">Hỏi trợ lý<ArrowRight size={16} /></Link></aside>
  </div>;
}
