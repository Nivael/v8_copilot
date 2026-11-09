import type {OfficialPDFAudit} from './STOfficialPDFAudit'
export function originalSourceTitle(title:string,audit:OfficialPDFAudit|null|undefined,sha256:string){return audit?.rows.some(r=>r.mirror_sha256===sha256)?'原记录镜像：'+title.replace('（发行人PDF镜像，官方原字节待补）',''):title}
export function officialCopyForSource(audit:OfficialPDFAudit|null|undefined,source:{sha256?:string;url:string}){return audit?.rows.find(r=>r.mirror_sha256===source.sha256||r.mirror_url===source.url.split('#')[0])}
