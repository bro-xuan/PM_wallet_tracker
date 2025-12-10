import mongoose, { Schema, Document, Model, Types } from 'mongoose';

export interface IWallet extends Document {
  _id: mongoose.Types.ObjectId;
  userId: Types.ObjectId;
  address: string;
  label: string;
  createdAt: Date;
  updatedAt: Date;
  isActive: boolean;
}

const WalletSchema = new Schema<IWallet>(
  {
    userId: {
      type: Schema.Types.ObjectId,
      ref: 'User',
      required: true,
      index: true,
    },
    address: {
      type: String,
      required: true,
      lowercase: true,
    },
    label: {
      type: String,
      required: false,
      default: '',
    },
    isActive: {
      type: Boolean,
      default: true,
    },
  },
  {
    timestamps: true,
  }
);

// Compound index to ensure unique addresses per user
WalletSchema.index({ userId: 1, address: 1 }, { unique: true });

const Wallet: Model<IWallet> = mongoose.models.Wallet || mongoose.model<IWallet>('Wallet', WalletSchema);

export default Wallet;

