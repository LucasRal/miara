import { guardSection } from "@/lib/guard";

/** Segment commercial (agent et coach) : owner, admin, sales. */
export default async function SalesLayout({ children }: LayoutProps<"/sales">) {
  const { denied } = await guardSection("/sales");
  return denied ?? children;
}
