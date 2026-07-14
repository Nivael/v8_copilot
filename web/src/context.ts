import type { NavigationFocus,ResearchContext } from './types'

export function readContext(search:string):ResearchContext {
  const params=new URLSearchParams(search)
  const event=params.get('event')
  const start=params.get('start')
  const end=params.get('end')
  return {
    ...(params.get('symbol')?{symbol:params.get('symbol')!}:{}),
    ...(event?{selected_event:{
      event_id:event,
      date:params.get('date')??undefined,
      title:params.get('title')??undefined,
    }}:{}),
    ...(params.get('episode')?{selected_episode:params.get('episode')!}:{}),
    ...(start||end?{date_range:{start:start??undefined,end:end??undefined}}:{}),
    ...(params.get('question')?{active_question:params.get('question')!}:{}),
    ...(params.get('answer')?{answer_card_id:params.get('answer')!}:{}),
    ...(params.get('object_kind')&&params.get('object_ref')?{object_scope:{
      kind:params.get('object_kind')!,ref:params.get('object_ref')!,
    }}:{}),
    ...(params.getAll('lens').length?{selected_lenses:params.getAll('lens')}:{}),
  }
}

export function readNavigationFocus(search:string):NavigationFocus|undefined {
  const params=new URLSearchParams(search)
  if(params.get('provenance'))return {kind:'provenance',ref:params.get('provenance')!}
  if(params.get('debt'))return {kind:'data_debt',ref:params.get('debt')!}
  return undefined
}

export function questionLink(context:ResearchContext,question:string) {
  const params=new URLSearchParams()
  if(context.symbol)params.set('symbol',context.symbol)
  if(context.selected_event){
    params.set('event',context.selected_event.event_id)
    if(context.selected_event.date)params.set('date',context.selected_event.date)
    if(context.selected_event.title)params.set('title',context.selected_event.title)
  }
  if(context.selected_episode)params.set('episode',context.selected_episode)
  if(context.date_range?.start)params.set('start',context.date_range.start)
  if(context.date_range?.end)params.set('end',context.date_range.end)
  if(context.answer_card_id)params.set('answer',context.answer_card_id)
  if(context.object_scope){
    params.set('object_kind',context.object_scope.kind)
    params.set('object_ref',context.object_scope.ref)
  }
  context.selected_lenses?.forEach(lens=>params.append('lens',lens))
  params.set('question',question)
  return `/legacy?${params}`
}
