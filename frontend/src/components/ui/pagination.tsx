import * as React from "react";
import { cn } from "@/lib/utils";

import { Button } from "@/components/ui/button";
import { ChevronLeftIcon, ChevronRightIcon, MoreHorizontalIcon } from "lucide-react";

function Pagination({ className, ...props }: React.ComponentProps<"nav">) {
  return (
    <nav
      role="navigation"
      aria-label="pagination"
      data-slot="pagination"
      className={cn("mx-auto flex w-full justify-center", className)}
      {...props}
    />
  );
}

function PaginationContent({ className, ...props }: React.ComponentProps<"ul">) {
  return (
    <ul
      data-slot="pagination-content"
      className={cn("flex items-center gap-0.5", className)}
      {...props}
    />
  );
}

function PaginationItem({ ...props }: React.ComponentProps<"li">) {
  return <li data-slot="pagination-item" {...props} />;
}

type PaginationLinkProps = {
  isActive?: boolean;
  /** N'a de sens que sur la forme bouton : un `<a>` ne se désactive pas. */
  disabled?: boolean;
} & Pick<React.ComponentProps<typeof Button>, "size"> &
  React.ComponentProps<"a">;

/**
 * Un lien de pagination — ou un bouton, quand la page se change sans changer
 * d'URL. Un `<a>` sans `href` n'est ni tabulable ni annoncé comme cliquable :
 * là où la pagination est un état local de l'écran, c'est un `<button>` qu'il
 * faut rendre, pas un lien décoratif.
 */
function PaginationLink({
  className,
  isActive,
  size = "icon",
  href,
  disabled,
  ...props
}: PaginationLinkProps) {
  const commun = {
    "aria-current": isActive ? ("page" as const) : undefined,
    "data-slot": "pagination-link",
    "data-active": isActive,
    className: cn(className),
  };
  return (
    <Button asChild variant={isActive ? "outline" : "ghost"} size={size}>
      {href === undefined ? (
        <button
          type="button"
          disabled={disabled}
          {...commun}
          {...(props as React.ComponentProps<"button">)}
        />
      ) : (
        <a href={href} {...commun} {...props} />
      )}
    </Button>
  );
}

function PaginationPrevious({
  className,
  text = "Précédent",
  ...props
}: React.ComponentProps<typeof PaginationLink> & { text?: string }) {
  return (
    <PaginationLink
      aria-label="Page précédente"
      size="default"
      className={cn("pl-1.5!", className)}
      {...props}
    >
      <ChevronLeftIcon data-icon="inline-start" />
      <span className="hidden sm:block">{text}</span>
    </PaginationLink>
  );
}

function PaginationNext({
  className,
  text = "Suivant",
  ...props
}: React.ComponentProps<typeof PaginationLink> & { text?: string }) {
  return (
    <PaginationLink
      aria-label="Page suivante"
      size="default"
      className={cn("pr-1.5!", className)}
      {...props}
    >
      <span className="hidden sm:block">{text}</span>
      <ChevronRightIcon data-icon="inline-end" />
    </PaginationLink>
  );
}

function PaginationEllipsis({ className, ...props }: React.ComponentProps<"span">) {
  return (
    <span
      aria-hidden
      data-slot="pagination-ellipsis"
      className={cn(
        "flex size-8 items-center justify-center [&_svg:not([class*='size-'])]:size-4",
        className
      )}
      {...props}
    >
      <MoreHorizontalIcon />
      <span className="sr-only">Pages omises</span>
    </span>
  );
}

export {
  Pagination,
  PaginationContent,
  PaginationEllipsis,
  PaginationItem,
  PaginationLink,
  PaginationNext,
  PaginationPrevious,
};
