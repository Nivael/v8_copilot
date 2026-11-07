import type {KeyboardEvent} from 'react'

export function scrollTable(event:KeyboardEvent<HTMLDivElement>){
  if(event.target!==event.currentTarget||event.ctrlKey||event.metaKey||event.altKey||event.shiftKey)return
  const page=Math.max(40,event.currentTarget.clientHeight-40)
  const moves:Record<string,[number,number]>={ArrowLeft:[-40,0],ArrowRight:[40,0],ArrowUp:[0,-40],ArrowDown:[0,40],PageUp:[0,-page],PageDown:[0,page]}
  const move=moves[event.key]
  if(!move)return
  event.preventDefault()
  event.currentTarget.scrollBy({left:move[0],top:move[1],behavior:'auto'})
}
