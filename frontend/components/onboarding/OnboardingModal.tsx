"use client"

import { useState } from "react"
import {
    Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import {
    Sparkles, MessageSquare, Headphones, Users, BarChart2, BookOpen, UserCog,
    ChevronLeft, ChevronRight, type LucideIcon,
} from "lucide-react"

type Step = { icon: LucideIcon; title: string; description: string }

const STEPS_BY_ROLE: Record<string, Step[]> = {
    user: [
        { icon: Sparkles, title: "Bienvenue sur SmartTicket", description: "Notre assistant IA répond à vos questions 24h/24, à partir de la base de connaissances du service." },
        { icon: MessageSquare, title: "Démarrez une conversation", description: "Cliquez sur « Nouveau chat » dans la barre latérale pour poser votre question à l'assistant." },
        { icon: Headphones, title: "Besoin d'un humain ?", description: "Si l'IA ne peut pas résoudre votre problème, transférez la conversation à un agent SAV en un clic." },
        { icon: BarChart2, title: "Suivez vos échanges", description: "Le tableau de bord liste toutes vos conversations, leur statut, et permet de les rechercher." },
    ],
    sav: [
        { icon: Headphones, title: "Bienvenue, agent SAV", description: "Vous prenez le relais de l'IA sur les conversations qu'elle n'a pas pu résoudre seule." },
        { icon: MessageSquare, title: "La file d'attente", description: "Chaque conversation transférée apparaît à gauche, avec sa raison de transfert (technique, complexe, sensible...)." },
        { icon: Sparkles, title: "Remettre à l'IA", description: "Une fois le problème résolu, vous pouvez remettre la conversation entre les mains de l'assistant." },
        { icon: BarChart2, title: "Analytics & Monitoring", description: "Suivez la performance du service et la santé de la base de connaissances depuis le menu Analyses." },
    ],
    superviseur: [
        { icon: UserCog, title: "Bienvenue, superviseur", description: "Vous encadrez l'équipe SAV, en plus de pouvoir traiter des tickets vous-même." },
        { icon: Users, title: "Gérer l'équipe", description: "Promouvez un utilisateur en agent SAV, ou retirez ce rôle, depuis le panneau en haut de votre tableau de bord." },
        { icon: Headphones, title: "Toujours agent SAV", description: "La file d'attente des tickets transférés reste accessible en bas de votre tableau de bord." },
        { icon: BarChart2, title: "Analytics & Monitoring", description: "Pilotez la performance de l'équipe et la santé de la base de connaissances." },
    ],
    admin: [
        { icon: UserCog, title: "Bienvenue, administrateur", description: "Vous avez un accès complet à la gestion des comptes, des rôles et des conversations." },
        { icon: Users, title: "Gérer les comptes", description: "Modifiez, supprimez ou changez le rôle de n'importe quel utilisateur, agent SAV ou superviseur." },
        { icon: BookOpen, title: "Base de connaissances", description: "Ingérez des documents ou des pages web pour enrichir les réponses de l'assistant IA." },
        { icon: BarChart2, title: "Analytics & Monitoring", description: "Exportez les dashboards en PDF ou CSV depuis les pages Analytique et Monitoring IA." },
    ],
}

export function onboardingStorageKey(userId: number, role: string): string {
    return `smartticket_onboarding_seen_${userId}_${role}`
}

export function hasSeenOnboarding(userId: number, role: string): boolean {
    if (typeof window === "undefined") return true
    return window.localStorage.getItem(onboardingStorageKey(userId, role)) === "1"
}

export default function OnboardingModal({ userId, role }: { userId: number; role: string }) {
    const steps = STEPS_BY_ROLE[role] ?? STEPS_BY_ROLE.user
    // OnboardingModal ne monte qu'une fois `user` chargé (voir dashboard/page.tsx), donc
    // userId/role sont déjà stables au premier rendu — un état initial paresseux suffit,
    // pas besoin d'un effet pour "rattraper" une valeur qui ne changera pas après coup.
    const [open, setOpen] = useState(() => !hasSeenOnboarding(userId, role))
    const [stepIndex, setStepIndex] = useState(0)

    const close = () => {
        setOpen(false)
        window.localStorage.setItem(onboardingStorageKey(userId, role), "1")
    }

    const step = steps[stepIndex]
    const isLast = stepIndex === steps.length - 1
    const Icon = step.icon

    return (
        <Dialog open={open} onOpenChange={(next) => { if (!next) close() }}>
            <DialogContent className="sm:max-w-md">
                <DialogHeader>
                    <div className="flex items-center gap-3 mb-1">
                        <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center flex-shrink-0">
                            <Icon className="h-5 w-5 text-primary" />
                        </div>
                        <DialogTitle>{step.title}</DialogTitle>
                    </div>
                    <DialogDescription>{step.description}</DialogDescription>
                </DialogHeader>

                <div className="flex items-center justify-center gap-1.5 py-2">
                    {steps.map((_, i) => (
                        <div
                            key={i}
                            className={`h-1.5 rounded-full transition-all ${i === stepIndex ? "w-6 bg-primary" : "w-1.5 bg-muted"}`}
                        />
                    ))}
                </div>

                <DialogFooter className="flex-row items-center justify-between sm:justify-between gap-2">
                    <Button variant="ghost" size="sm" onClick={close}>
                        Passer
                    </Button>
                    <div className="flex items-center gap-2">
                        {stepIndex > 0 && (
                            <Button variant="outline" size="sm" onClick={() => setStepIndex((i) => i - 1)}>
                                <ChevronLeft className="h-4 w-4 mr-1" /> Précédent
                            </Button>
                        )}
                        {isLast ? (
                            <Button size="sm" onClick={close}>Terminé</Button>
                        ) : (
                            <Button size="sm" onClick={() => setStepIndex((i) => i + 1)}>
                                Suivant <ChevronRight className="h-4 w-4 ml-1" />
                            </Button>
                        )}
                    </div>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    )
}
