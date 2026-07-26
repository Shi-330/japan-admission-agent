import { Button } from '@/components/ui/button';

/**
 * Shared empty-state placeholder used across all tabs.
 * Renders a centered icon, title, description, and optional CTA button.
 */
export default function EmptyState({ icon: Icon, title, description, action }) {
  return (
    <div className="flex-1 flex items-center justify-center p-8">
      <div className="text-center max-w-sm">
        {Icon && (
          <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-muted mb-4">
            <Icon size={26} className="text-muted-foreground" strokeWidth={1.5} />
          </div>
        )}
        <h3 className="text-base font-semibold text-foreground mb-1.5">{title}</h3>
        {description && (
          <p className="text-sm text-muted-foreground mb-5 leading-relaxed">{description}</p>
        )}
        {action && (
          <Button onClick={action.onClick} size="sm" className="px-5">
            {action.label}
          </Button>
        )}
      </div>
    </div>
  );
}
