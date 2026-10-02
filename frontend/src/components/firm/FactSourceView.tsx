import type { FactSourceOut } from '@/api/types'
import { SourceBody } from '@/components/firm/SourceBody'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { SOURCE_LABELS } from '@/lib/labels'

/** The cited source, plus a tab for each source that corroborates it. */
export function FactSourceView({ data }: { data: FactSourceOut }) {
  const { fact, source, corroborating } = data
  const cited = <SourceBody source={source} quote={fact.quote} citedPageNo={fact.page_no} />
  if (corroborating.length === 0) return cited

  return (
    <Tabs defaultValue={String(source.source_id)}>
      <TabsList>
        <TabsTrigger value={String(source.source_id)}>Cited source</TabsTrigger>
        {corroborating.map((other) => (
          <TabsTrigger key={other.source_id} value={String(other.source_id)}>
            Also in {SOURCE_LABELS[other.source_type]}
          </TabsTrigger>
        ))}
      </TabsList>
      <TabsContent value={String(source.source_id)} className="pt-3">
        {cited}
      </TabsContent>
      {corroborating.map((other) => (
        <TabsContent key={other.source_id} value={String(other.source_id)} className="pt-3">
          <SourceBody source={other} quote={null} citedPageNo={null} />
        </TabsContent>
      ))}
    </Tabs>
  )
}
