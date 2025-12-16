import CredentialsProvider from 'next-auth/providers/credentials';
import { MongoDBAdapter } from '@auth/mongodb-adapter';
import clientPromise from './mongodb';
import bcrypt from 'bcryptjs';

export const authOptions = {
  adapter: MongoDBAdapter(clientPromise),
  providers: [
    CredentialsProvider({
      name: 'Credentials',
      credentials: {
        email: { label: 'Email', type: 'email' },
        password: { label: 'Password', type: 'password' },
      },
      async authorize(credentials) {
        if (!credentials?.email || !credentials?.password) {
          throw new Error('Email and password required');
        }

        const email = String(credentials.email).toLowerCase();
        const password = String(credentials.password);

        const client = await clientPromise;
        const db = client.db(process.env.MONGODB_DB_NAME || 'pm-wallet-tracker');
        const usersCollection = db.collection('users');

        // Find user by email
        const user = await usersCollection.findOne({
          email: email,
        });

        if (!user) {
          throw new Error('Invalid email or password');
        }

        // Check password
        if (!user.password) {
          throw new Error('Invalid email or password');
        }

        const isValid = await bcrypt.compare(
          password,
          user.password
        );

        if (!isValid) {
          throw new Error('Invalid email or password');
        }

        return {
          id: user._id.toString(),
          email: user.email,
          name: user.name || null,
        };
      },
    }),
  ],
  session: {
    strategy: 'jwt' as const,
  },
  pages: {
    signIn: '/',
  },
  callbacks: {
    async jwt({ token, user }: any) {
      if (user) {
        token.id = user.id;
        token.email = user.email;
      }
      return token;
    },
    async session({ session, token }: any) {
      if (session.user) {
        session.user.id = token.id as string;
        session.user.email = token.email as string;
      }
      return session;
    },
  },
  secret: process.env.NEXTAUTH_SECRET,
};

