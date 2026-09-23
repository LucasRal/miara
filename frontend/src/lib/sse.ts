/**
 * Client SSE pour les endpoints qui diffusent un POST.
 *
 * `EventSource` ne sait pas poster : on lit donc la réponse en flux et on
 * découpe les trames « event: X\ndata: {...} » à la main. Les cookies httpOnly
 * suivent la requête comme pour n'importe quel fetch same-origin.
 */
export interface SseHandlers<T> {
  onEvent: (event: string, data: T) => void;
  onError?: (message: string) => void;
}

export async function streamPost<T>(
  path: string,
  body: unknown,
  { onEvent, onError }: SseHandlers<T>,
  signal?: AbortSignal
): Promise<void> {
  const res = await fetch(`/api/v1${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });
  if (!res.ok || !res.body) {
    onError?.(`Le serveur a répondu ${res.status}.`);
    return;
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let tampon = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    tampon += decoder.decode(value, { stream: true });

    // Une trame se termine par une ligne vide ; le reste attend la suite.
    let coupure: number;
    while ((coupure = tampon.indexOf("\n\n")) !== -1) {
      const trame = tampon.slice(0, coupure);
      tampon = tampon.slice(coupure + 2);
      let event = "message";
      const donnees: string[] = [];
      for (const ligne of trame.split("\n")) {
        if (ligne.startsWith("event:")) event = ligne.slice(6).trim();
        else if (ligne.startsWith("data:")) donnees.push(ligne.slice(5).trim());
      }
      if (donnees.length === 0) continue;
      try {
        onEvent(event, JSON.parse(donnees.join("\n")) as T);
      } catch {
        onError?.("Trame illisible reçue du serveur.");
      }
    }
  }
}
