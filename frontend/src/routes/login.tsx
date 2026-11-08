import { createFileRoute } from "@tanstack/react-router";
import { EmailAuthForm } from "@/components/EmailAuthForm";

export const Route = createFileRoute("/login")({
  component: () => <EmailAuthForm mode="login" />,
});
