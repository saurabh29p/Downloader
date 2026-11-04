import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import type { ReactElement } from "react";

import messages from "@/messages/en.json";

export function renderWithProviders(
  ui: ReactElement,
  client = new QueryClient({ defaultOptions: { queries: { retry: false } } }),
) {
  return {
    client,
    ...render(
      <NextIntlClientProvider locale="en" messages={messages}>
        <QueryClientProvider client={client}>{ui}</QueryClientProvider>
      </NextIntlClientProvider>,
    ),
  };
}
