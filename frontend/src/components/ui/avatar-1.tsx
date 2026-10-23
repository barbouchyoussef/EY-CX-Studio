import clsx from "clsx";
import { Bot } from "lucide-react";
import { Skeleton } from "./skeleton-1";

interface AvatarProps {
  placeholder?: boolean;
  size?: number;
  src?: string;
  alt?: string;
  chatbot?: boolean;
  className?: string;
}

export const Avatar = ({
  placeholder = false,
  size = 28,
  src,
  alt = "Avatar",
  chatbot = false,
  className,
}: AvatarProps) => {
  if (placeholder) {
    return <Skeleton rounded height={size} width={size} className="border border-gray-alpha-400" />;
  }

  return (
    <span
      className={clsx(
        "inline-flex overflow-hidden rounded-full border border-gray-alpha-400 duration-200",
        chatbot && "items-center justify-center bg-gradient-to-br from-violet-600 to-indigo-600 text-white",
        className
      )}
      style={{ width: size, height: size }}
    >
      {src ? (
        <img src={src} alt={alt} className="h-full w-full object-cover" />
      ) : chatbot ? (
        <Bot className="h-[60%] w-[60%]" />
      ) : null}
    </span>
  );
};
