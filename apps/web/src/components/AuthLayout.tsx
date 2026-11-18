"use client";

import React from "react";
import Link from "next/link";
import { GraduationCap, ShieldCheck, FileCheck2, BookOpen, ArrowLeft } from "lucide-react";
import { ThemeToggle } from "./ThemeToggle";

interface AuthLayoutProps { children: React.ReactNode; introContent?: React.ReactNode; }

export function AuthLayout({ children, introContent }: AuthLayoutProps) {
  return <div className="campus-auth">
    <header className="campus-auth-header"><span><GraduationCap size={17} />Cổng Thông Tin Học Vụ Trực Tuyến · HUCE</span><span><Link href="/chat">Hướng dẫn sử dụng</Link><ThemeToggle /></span></header>
    <main className="campus-auth-main"><div className="campus-auth-frame">
      <section className="campus-auth-intro">
        <Link href="/" className="campus-auth-brand"><GraduationCap size={28} /><div><strong>Campus 24/7</strong><small>ĐẠI HỌC XÂY DỰNG HÀ NỘI</small></div></Link>
        {introContent || <><p>Không gian số Dịch vụ sinh viên & Học vụ trực tuyến · ĐH Xây dựng Hà Nội (HUCE). Tra cứu thông tin và chuẩn bị thủ tục học vụ trong cùng một không gian.</p>
          <div className="campus-auth-benefits">
            <div><BookOpen size={22} /><section><strong>Trợ lý học vụ có nguồn</strong><p>Tra cứu quy chế đào tạo và đối chiếu căn cứ văn bản.</p></section></div>
            <div><ShieldCheck size={22} /><section><strong>Kiểm soát thông tin cá nhân</strong><p>Quản lý quyền riêng tư và lựa chọn sử dụng dữ liệu của bạn.</p></section></div>
            <div><FileCheck2 size={22} /><section><strong>Dịch vụ một cửa</strong><p>Chuẩn bị bản nháp, xem trước và xác nhận trước khi gửi hồ sơ.</p></section></div>
          </div></>}
        <Link href="/" className="inline-flex items-center gap-2 text-sm mt-auto"><ArrowLeft size={16} />Quay lại trang chủ</Link>
      </section>
      <section className="campus-auth-form">{children}</section>
    </div></main>
    <footer className="campus-auth-footer"><span>© 2026 Trường Đại học Xây dựng Hà Nội · Campus 24/7</span><Link href="/privacy">Chính sách quyền riêng tư</Link></footer>
  </div>;
}
