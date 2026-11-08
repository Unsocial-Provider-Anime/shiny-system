export const profileQueryKey = ["profile"] as const;

export interface Profile {
  email: string;
}

export async function fetchProfile(): Promise<Profile | null> {
  const response = await fetch("/api/v1/auth/me", {
    credentials: "same-origin",
  });
  if (response.status === 401) {
    return null;
  }
  if (!response.ok) {
    throw new Error("Unable to load your account.");
  }
  const result: unknown = await response.json();
  if (
    typeof result !== "object" ||
    result === null ||
    !("user" in result) ||
    typeof result.user !== "object" ||
    result.user === null ||
    !("email" in result.user) ||
    typeof result.user.email !== "string"
  ) {
    throw new Error("The account response was invalid.");
  }
  return { email: result.user.email };
}
