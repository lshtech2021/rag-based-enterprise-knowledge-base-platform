"use client";

import type { Components } from "react-markdown";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

const components: Components = {
  h1: ({ children }) => (
    <h1 className="font-display text-2xl text-ink first:mt-0">{children}</h1>
  ),
  h2: ({ children }) => (
    <h2 className="font-display mt-5 text-xl text-ink first:mt-0">{children}</h2>
  ),
  h3: ({ children }) => (
    <h3 className="mt-4 text-base font-semibold text-ink first:mt-0">{children}</h3>
  ),
  p: ({ children }) => <p className="text-ink">{children}</p>,
  ul: ({ children }) => (
    <ul className="list-disc space-y-1 pl-5 text-ink">{children}</ul>
  ),
  ol: ({ children }) => (
    <ol className="list-decimal space-y-1 pl-5 text-ink">{children}</ol>
  ),
  li: ({ children }) => <li className="leading-relaxed">{children}</li>,
  strong: ({ children }) => (
    <strong className="font-semibold text-ink">{children}</strong>
  ),
  em: ({ children }) => <em className="italic text-ink">{children}</em>,
  a: ({ href, children }) => (
    <a
      href={href}
      className="text-teal underline underline-offset-2 hover:text-teal-bright"
      target="_blank"
      rel="noopener noreferrer"
    >
      {children}
    </a>
  ),
  code: ({ className, children }) => {
    const isBlock = Boolean(className?.includes("language-"));
    if (isBlock) {
      return (
        <code className="block overflow-x-auto rounded-none bg-paper px-3 py-2 font-mono text-xs text-ink">
          {children}
        </code>
      );
    }
    return (
      <code className="rounded-none bg-paper px-1 py-0.5 font-mono text-[0.85em] text-ink">
        {children}
      </code>
    );
  },
  pre: ({ children }) => (
    <pre className="overflow-x-auto border border-line bg-paper p-3 text-xs">
      {children}
    </pre>
  ),
  blockquote: ({ children }) => (
    <blockquote className="border-l-2 border-teal pl-3 text-muted">{children}</blockquote>
  ),
  hr: () => <hr className="border-line" />,
};

type MarkdownContentProps = {
  markdown: string;
  className?: string;
};

export function MarkdownContent({ markdown, className }: MarkdownContentProps) {
  const wrapperClass = ["space-y-3 text-sm leading-relaxed text-ink", className]
    .filter(Boolean)
    .join(" ");

  return (
    <div className={wrapperClass}>
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {markdown}
      </ReactMarkdown>
    </div>
  );
}
