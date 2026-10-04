import { useParams } from "react-router-dom";
import { webPageUrl } from "../api";
import { PAGE_SANDBOX } from "./ChatWidgets";

export default function PreviewView() {
  const { id } = useParams();
  if (!id) return null;
  return (
    <iframe
      className="preview-frame"
      src={webPageUrl(id)}
      title="Web page preview"
      sandbox={PAGE_SANDBOX}
    />
  );
}
