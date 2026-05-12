declare module "streamdown" {
    import type { ComponentType, ReactNode } from "react"

export interface StreamdownProps {
        children?: ReactNode
        className?: string
        animated?: boolean
        isAnimating?: boolean
    }

    export const Streamdown: ComponentType<StreamdownProps>
}
