import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

/**
 * Lien d'évitement : invisible tant qu'il n'a pas le focus, puis posé
 * au-dessus de la page.
 *
 * `fixed` une fois visible plutôt que dans le flux : apparaître ne doit
 * décaler aucune mise en page. Écrit une fois — il y en a deux, celui de la
 * coquille (« Aller au contenu ») et celui du chat (« Aller à la zone de
 * saisie »), et ils doivent se ressembler.
 */
export function SkipLink({
  href,
  children,
  className,
}: {
  href: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <a
      href={href}
      className={cn(
        buttonVariants({ size: "sm" }),
        "sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-50",
        className
      )}
    >
      {children}
    </a>
  );
}
