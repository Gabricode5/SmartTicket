// Helpers partagés pour le système de pôles (feature/poles, étape 5 UI). Toute la logique
// de "qui voit/peut quoi" vit ici pour rester alignée avec dependencies.py côté backend
// (is_pole_unrestricted, is_manager) — un seul endroit à mettre à jour si ces règles
// évoluent, plutôt que de la logique dupliquée dans chaque composant.
import type { CurrentUser } from "@/hooks/useCurrentUser"

export type Pole = { id: number; nom: string; is_global: boolean }

/** Un manager = un superviseur avec au moins un pôle géré (manager_poles côté backend). */
export function isManager(user: Pick<CurrentUser, "managed_poles"> | null | undefined): boolean {
    return !!user?.managed_poles && user.managed_poles.length > 0
}

/**
 * Aucun cloisonnement par pôle ne s'applique à ce compte — miroir exact de
 * dependencies.is_pole_unrestricted côté backend : le super admin (rôle admin), ou un
 * superviseur qui n'est jamais devenu manager (garde la visibilité totale qu'il avait
 * déjà avant les pôles).
 */
export function isPoleUnrestricted(user: Pick<CurrentUser, "role" | "managed_poles"> | null | undefined): boolean {
    if (!user) return false
    if (user.role === "admin") return true
    return user.role === "superviseur" && !isManager(user)
}

/** Le sélecteur de pôle n'a de sens à afficher que si la feature est active ET que ce
 * compte a un choix réel à faire (unrestricted = choix parmi tous les pôles existants ;
 * manager avec 2+ pôles = choix parmi les siens). Un manager à un seul pôle ou un compte
 * scopé à un pôle unique (sav) n'a rien à choisir : pas de sélecteur, juste une valeur
 * fixe affichée en lecture seule. */
export function shouldShowPoleSelector(
    user: Pick<CurrentUser, "role" | "poles_enabled" | "managed_poles"> | null | undefined,
): boolean {
    if (!user?.poles_enabled) return false
    if (isPoleUnrestricted(user)) return true
    return (user.managed_poles?.length ?? 0) > 1
}
