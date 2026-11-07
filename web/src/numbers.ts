/** Group the integer part without converting to floating point or touching fractional digits. */
export function formatShareCount(value:string|null|undefined):string{
  if(value==null)return '—'
  if(!/^-?\d+(?:\.\d+)?$/.test(value))return value
  const [whole,fraction]=value.split('.')
  return whole.replace(/\B(?=(\d{3})+(?!\d))/g,',')+(fraction==null?'':`.${fraction}`)
}
