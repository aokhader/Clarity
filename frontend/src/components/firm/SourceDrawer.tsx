import { useParams } from 'react-router'

import { useFrozenFactSource } from '@/api/chat'
import { ApiError } from '@/api/client'
import { useFactSource } from '@/api/facts'
import { FactSourceView } from '@/components/firm/FactSourceView'
import { FactSummary } from '@/components/firm/FactSummary'
import { SourceNavigator } from '@/components/firm/SourceNavigator'
import { LoadError } from '@/components/shared/LoadError'
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from '@/components/ui/sheet'
import { Skeleton } from '@/components/ui/skeleton'
import { returnFocusFromDrawer, useSourceDrawer } from '@/lib/useSourceDrawer'

/** The matter in the route; the drawer is only mounted on a matter page. */
function useMatterIdParam(): number | null {
  const matterId = Number(useParams().matterId)
  return Number.isInteger(matterId) && matterId > 0 ? matterId : null
}

/**
 * Why a source is not there. A frozen source's 404 carries the server's reason (the fact
 * was re-read away, or the thread does not cite it); a live one's is always the same.
 */
function notFoundText(error: ApiError, frozen: boolean): string {
  if (!frozen) return 'This fact cannot be shown: it is missing or has no source to cite.'
  return typeof error.detail === 'string' && error.detail !== '' ? error.detail : 'This source is no longer in the file.'
}

/**
 * The right-hand drawer every source chip opens. It follows `?fact=ID`, so a source
 * view can be linked, and Escape, a click outside, or the back button closes it. Focus
 * then returns to the chip that opened it. Opened with an item's list of sources, it
 * steps through them; the navigator sits outside the loaded branch, so it stays put
 * while the next source loads (D46). Opened from a closed chat thread, it shows the copy
 * frozen when the thread closed, and says so (D54).
 */
export function SourceDrawer() {
  const { factId, frozenThreadId, close } = useSourceDrawer()
  const matterId = useMatterIdParam()
  const frozen = frozenThreadId !== null
  // Only one of the two loads; the other stays idle.
  const live = useFactSource(frozen ? null : factId)
  const frozenSource = useFrozenFactSource(frozen ? matterId : null, frozenThreadId, factId)
  const source = frozen ? frozenSource : live

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
        {frozen && (
          <p className="border-b px-6 py-3 pr-16 text-sm text-muted-foreground">As cited when this thread was closed.</p>
        )}
        <SourceNavigator />
        {source.isSuccess ? (
          <>
            <SheetHeader className="border-b px-6 pr-16">
              <SheetTitle className="text-lg text-balance">{source.data.fact.title}</SheetTitle>
              <SheetDescription asChild>
                <div>
                  <FactSummary fact={source.data.fact} />
                </div>
              </SheetDescription>
            </SheetHeader>
            <div className="px-6 py-5">
              <FactSourceView key={source.data.fact.id} data={source.data} />
            </div>
          </>
        ) : (
          <>
            <SheetHeader className="px-6 pr-16">
              <SheetTitle>{source.isError ? 'Source unavailable' : 'Loading the source'}</SheetTitle>
              <SheetDescription className="sr-only">The record this fact came from.</SheetDescription>
            </SheetHeader>
            <div className="space-y-3 px-6 py-5">
              {source.isError &&
                (source.error instanceof ApiError && source.error.status === 404 ? (
                  <p className="text-sm text-muted-foreground">{notFoundText(source.error, frozen)}</p>
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
