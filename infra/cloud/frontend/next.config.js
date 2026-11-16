// Portable Next.js config for the snapshot that infra/cloud/build_frontend.sh builds outside apps/web.
// Modules are resolved from the pnpm install in apps/web; CAMPUS247_ROOT is the repository root on the server.
const path = require("node:path");
const root = process.env.CAMPUS247_ROOT || path.resolve(process.cwd(), "../../../..");
const modules = path.join(root, "apps/web/node_modules");
module.exports = {
  outputFileTracingRoot: root,
  experimental: { cpus: 2, webpackBuildWorker: false },
  webpack(config) {
    config.cache = false;
    config.resolve.modules.push(modules);
    config.resolveLoader.modules.push(modules);
    return config;
  },
};
