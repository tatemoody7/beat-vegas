import { redirect } from "next/navigation";

// The glossary retired into Track record, where the numbers it defines
// actually are. Kept as a redirect so old links land on the open reference.
export default async function Moved() {
  redirect("/proof#glossary");
}
