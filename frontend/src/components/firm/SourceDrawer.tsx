import { ApiError } from '@/api/client'
import { useFactSource } from '@/api/facts'
import { FactSourceView } from '@/components/firm/FactSourceView'
import { FactSummary } from '@/components/firm/FactSummary'
import { LoadError } from '@/components/shared/LoadError'
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from '@/components/ui/sheet'
import { Skeleton } from '@/components/ui/skeleton'
import { returnFocusFromDrawer, useSourceDrawer } from '@/lib/useSourceDrawer'

/**
 * The right-hand drawer every source chip opens. It follows `?fact=ID`, so a source
 * view can be linked, and Escape, a click outside, or the back button closes it. Focus
 * then returns to the chip that opened it.
 */
export function SourceDrawer() {
  const { factId, close } = useSourceDrawer()
  const source = useFactSource(factId)

  return (
    <Sheet open={factId !== null} onOpenChange={(open) => !open && close()}>
      <SheetContent
        side="right"
        className="w-[720px] gap-0 overflow-y-auto data-[side=right]:sm:max-w-[min(720px,95vw)]"
        // The drawer has no trigger of its own, so focus goes back to the chip that opened it.
        onCloseAutoFocus={(event) => {
          event.preventDefault()
          returnFocusFromDrawer()
        }}
      >
        {source.isSuccess ? (
          <>
            <SheetHeader className="border-b pr-12">
              <SheetTitle className="text-lg">{source.data.fact.title}</SheetTitle>
              <SheetDescription asChild>
                <div>
                  <FactSummary fact={source.data.fact} />
                </div>
              </SheetDescription>
            </SheetHeader>
            <div className="p-4">
              <FactSourceView key={source.data.fact.id} data={source.data} />
            </div>
          </>
        ) : (
          <>
            <SheetHeader>
              <SheetTitle>{source.isError ? 'Source unavailable' : 'Loading the source'}</SheetTitle>
              <SheetDescription className="sr-only">The record this fact came from.</SheetDescription>
            </SheetHeader>
            <div className="space-y-3 p-4">
              {source.isError &&
                (source.error instanceof ApiError && source.error.status === 404 ? (
                  <p className="text-sm text-muted-foreground">
                    This fact cannot be shown: it is missing or has no source to cite.
                  </p>
                ) : (
                  <LoadError what="the source" error={source.error} onRetry={() => void source.refetch()} />
                ))}
              {source.isPending && (
                <>
                  <Skeleton className="h-6 w-2/3" />
                  <Skeleton className="h-96" />
                </>
              )}
            </div>
          </>
        )}
      </SheetContent>
    </Sheet>
  )
}
