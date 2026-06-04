import next from "eslint-config-next";
import prettier from "eslint-config-prettier";

// Next 16 ships native flat-config arrays — spread them directly (FlatCompat
// hits a circular-JSON bug with ESLint 9). Prettier last to disable any
// formatting rules that would fight the formatter.
const config = [
  { ignores: [".next/**", "node_modules/**", "prisma/generated/**"] },
  ...next,
  prettier,
];

export default config;
