import { guardSection } from "@/lib/guard";

/** Segment RH : owner, admin, hr. Toute autre URL directe rend l'écran d'accès refusé. */
export default async function HrLayout({ children }: LayoutProps<"/hr">) {
  const { denied } = await guardSection("/hr");
  return denied ?? children;
}
