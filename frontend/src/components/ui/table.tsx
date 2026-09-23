"use client";

import * as React from "react";

import { ScrollX } from "@/components/ui/scroll-x";
import { cn } from "@/lib/utils";

function Table({
  className,
  label = "Tableau",
  borne = false,
  sommet,
  ...props
}: React.ComponentProps<"table"> & {
  /** Nom de la zone défilante, annoncé quand le tableau déborde. */
  label?: string;
  /**
   * Borner la hauteur du tableau et le faire défiler dans son cadre (≥ `sm`).
   * Ce qui suit — la pagination au premier chef — reste alors à l'écran.
   */
  borne?: boolean;
  /** Valeur qui, en changeant, ramène le cadre en haut (numéro de page). */
  sommet?: unknown;
}) {
  return (
    <ScrollX data-slot="table-container" label={label} borne={borne} entete sommet={sommet}>
      <table
        data-slot="table"
        className={cn("w-full caption-bottom text-sm", className)}
        {...props}
      />
    </ScrollX>
  );
}

function TableHeader({ className, ...props }: React.ComponentProps<"thead">) {
  return (
    <thead
      data-slot="table-header"
      // Collant : que le cadre défile ou que ce soit la page, la colonne lue
      // reste identifiable. L'ombre de bord du cadre passe dessous.
      className={cn("sticky top-0 z-20 bg-background [&_tr]:border-b", className)}
      {...props}
    />
  );
}

function TableBody({ className, ...props }: React.ComponentProps<"tbody">) {
  return (
    <tbody
      data-slot="table-body"
      className={cn("[&_tr:last-child]:border-0", className)}
      {...props}
    />
  );
}

function TableFooter({ className, ...props }: React.ComponentProps<"tfoot">) {
  return (
    <tfoot
      data-slot="table-footer"
      className={cn("border-t bg-muted/50 font-medium [&>tr]:last:border-b-0", className)}
      {...props}
    />
  );
}

function TableRow({ className, ...props }: React.ComponentProps<"tr">) {
  return (
    <tr
      data-slot="table-row"
      className={cn(
        "border-b transition-colors hover:bg-muted/50 has-aria-expanded:bg-muted/50 data-[state=selected]:bg-muted",
        className
      )}
      {...props}
    />
  );
}

function TableHead({ className, ...props }: React.ComponentProps<"th">) {
  return (
    <th
      data-slot="table-head"
      className={cn(
        "h-10 px-2 text-left align-middle font-medium whitespace-nowrap text-foreground [&:has([role=checkbox])]:pr-0",
        className
      )}
      {...props}
    />
  );
}

function TableCell({ className, ...props }: React.ComponentProps<"td">) {
  return (
    <td
      data-slot="table-cell"
      className={cn("p-2 align-middle whitespace-nowrap [&:has([role=checkbox])]:pr-0", className)}
      {...props}
    />
  );
}

function TableCaption({ className, ...props }: React.ComponentProps<"caption">) {
  return (
    <caption
      data-slot="table-caption"
      className={cn("mt-4 text-sm text-muted-foreground", className)}
      {...props}
    />
  );
}

export { Table, TableHeader, TableBody, TableFooter, TableHead, TableRow, TableCell, TableCaption };
