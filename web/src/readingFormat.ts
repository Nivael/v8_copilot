export function percent(value:number|null|undefined){return value==null?'待更新':`${value>0?'+':''}${value.toFixed(2)}%`}
