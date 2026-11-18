import type { MetadataRoute } from "next";

/** Lets a phone or desktop browser install Campus 24/7 as an app. The icon is the product's own mark, not the university's logo. */
export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Campus 24/7",
    short_name: "Campus 24/7",
    description: "Trợ lý học vụ và cổng dịch vụ số (bản thử nghiệm, không phải dịch vụ chính thức của nhà trường).",
    lang: "vi",
    dir: "ltr",
    start_url: "/?source=pwa",
    scope: "/",
    display: "standalone",
    background_color: "#f3f1ea",
    theme_color: "#0e3b3f",
    categories: ["education"],
    icons: [
      { src: "/icons/icon-192.png", sizes: "192x192", type: "image/png", purpose: "any" },
      { src: "/icons/icon-512.png", sizes: "512x512", type: "image/png", purpose: "any" },
      { src: "/icons/icon-maskable-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
    ],
  };
}
