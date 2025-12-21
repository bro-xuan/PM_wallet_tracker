// MongoDB connection singleton
import { MongoClient } from 'mongodb';

if (!process.env.MONGODB_URI) {
  throw new Error('Please add your Mongo URI to .env.local');
}

const uri = process.env.MONGODB_URI;
const options = {
  // Connection timeout settings
  connectTimeoutMS: 30000, // 30 seconds to establish connection
  serverSelectionTimeoutMS: 30000, // 30 seconds to select server
  socketTimeoutMS: 45000, // 45 seconds for socket operations
  
  // Connection pool settings
  maxPoolSize: 10, // Maximum number of connections in pool
  minPoolSize: 1, // Minimum number of connections in pool
  
  // Retry settings
  retryWrites: true,
  retryReads: true,
  
  // Heartbeat settings (keep connection alive)
  heartbeatFrequencyMS: 10000, // Check connection health every 10 seconds
};

let client: MongoClient;
let clientPromise: Promise<MongoClient>;

if (process.env.NODE_ENV === 'development') {
  // In development mode, use a global variable so that the value
  // is preserved across module reloads caused by HMR (Hot Module Replacement).
  const globalWithMongo = global as typeof globalThis & {
    _mongoClientPromise?: Promise<MongoClient>;
  };

  if (!globalWithMongo._mongoClientPromise) {
    client = new MongoClient(uri, options);
    globalWithMongo._mongoClientPromise = client.connect();
  }
  clientPromise = globalWithMongo._mongoClientPromise;
} else {
  // In production mode, it's best to not use a global variable.
  client = new MongoClient(uri, options);
  clientPromise = client.connect();
}

export default clientPromise;

