import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Build enxuto para Docker: copia só o runtime necessário em .next/standalone.
  // (Next 16 não roda ESLint no build, então o débito de lint não trava o deploy.)
  output: "standalone",
};

export default nextConfig;
