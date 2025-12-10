import mongoose, { Schema, Document, Model, Types } from 'mongoose';

export interface ITelegramAccount extends Document {
  _id: mongoose.Types.ObjectId;
  userId: Types.ObjectId;
  chatId: string;
  username: string | null;
  linkedAt: Date;
  isActive: boolean;
}

const TelegramAccountSchema = new Schema<ITelegramAccount>(
  {
    userId: {
      type: Schema.Types.ObjectId,
      ref: 'User',
      required: true,
      index: true,
    },
    chatId: {
      type: String,
      required: true,
      unique: true,
    },
    username: {
      type: String,
      required: false,
    },
    linkedAt: {
      type: Date,
      default: Date.now,
    },
    isActive: {
      type: Boolean,
      default: true,
    },
  },
  {
    timestamps: false,
  }
);

const TelegramAccount: Model<ITelegramAccount> =
  mongoose.models.TelegramAccount || mongoose.model<ITelegramAccount>('TelegramAccount', TelegramAccountSchema);

export default TelegramAccount;

