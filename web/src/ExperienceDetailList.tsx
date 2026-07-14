interface ExperienceDetailListProps {
  title:string
  values:string[]
}

export function ExperienceDetailList({title,values}:ExperienceDetailListProps){
  if(!values.length)return null
  return <section><h4>{title}</h4><ul>{values.map(value=><li key={value}>{value}</li>)}</ul></section>
}
