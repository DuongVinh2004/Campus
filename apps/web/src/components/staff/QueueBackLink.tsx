"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { useStore } from "@/lib/store";
import { queuePosition } from "./queue-navigation";

export function QueueBackLink() {
  const { currentUser } = useStore();
  const [href, setHref] = useState("/dashboard");
  useEffect(() => {
    const saved = currentUser && queuePosition(currentUser.id);
    if (saved) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setHref(saved.url);
    }
  }, [currentUser]);
  return <Link href={href} scroll={false} className="mb-3 inline-flex items-center gap-2 text-sm text-slate-500 hover:text-blue-700">
    <ArrowLeft className="h-4 w-4" />Quay lại hàng chờ
  </Link>;
}
