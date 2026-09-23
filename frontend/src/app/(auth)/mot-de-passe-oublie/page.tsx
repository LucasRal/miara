import Link from "next/link";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

export const metadata = { title: "Mot de passe oublié · Miara" };

/**
 * Mot de passe oublié : la marche à suivre, faute de réinitialisation.
 *
 * Miara n'envoie pas encore de courriel — il n'y a ni endpoint de
 * réinitialisation ni service d'envoi côté backend. Plutôt qu'un lien qui
 * n'existe pas ou un formulaire qui ne mène nulle part, l'écran dit
 * exactement quoi faire et qui contacter. Le jour où l'envoi existe, c'est
 * cette page qui accueille le formulaire.
 */
export default function MotDePasseOubliePage() {
  return (
    <div className="flex flex-1 items-center justify-center bg-muted/40 p-4">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle asChild>
            <h1>Mot de passe oublié</h1>
          </CardTitle>
          <CardDescription>
            La réinitialisation par courriel n&apos;est pas encore disponible. Voici comment
            retrouver l&apos;accès à votre compte.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-3 text-sm">
          <p>
            <strong className="font-medium">Vous faites partie d&apos;une organisation.</strong>{" "}
            Demandez à une personne propriétaire ou administratrice de votre organisation de
            réinitialiser votre mot de passe. Elle vous retrouve dans Paramètres → Membres.
          </p>
          <p>
            <strong className="font-medium">Vous êtes seul sur votre organisation.</strong>{" "}
            Contactez l&apos;administrateur de la plateforme Miara : lui seul peut réattribuer un
            mot de passe sans passer par votre boîte mail.
          </p>
          <p className="text-muted-foreground">
            Votre organisation, vos offres et vos conversations ne sont pas perdues : seul
            l&apos;accès à votre compte l&apos;est.
          </p>
        </CardContent>
        <CardFooter className="mt-4">
          <Button asChild variant="outline" size="sm">
            <Link href="/login">Revenir à la connexion</Link>
          </Button>
        </CardFooter>
      </Card>
    </div>
  );
}
