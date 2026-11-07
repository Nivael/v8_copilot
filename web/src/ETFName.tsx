const names:Record<string,string>={
  '510300.SH':'华泰柏瑞沪深300ETF','510310.SH':'易方达沪深300ETF',
  '510330.SH':'华夏沪深300ETF','159919.SZ':'嘉实沪深300ETF',
  '510500.SH':'南方中证500ETF','159922.SZ':'嘉实中证500ETF',
  '512100.SH':'南方中证1000ETF','159845.SZ':'华夏中证1000ETF',
}
export function ETFName({code}:{code:string}){return <>{names[code]||'ETF名称待核对'}<small>{code}</small></>}
