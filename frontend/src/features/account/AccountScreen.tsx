import { ScreenTitle } from "@app/components/layout/ScreenTitle";
import { AchievementsSection } from "@app/features/account/AchievementsSection";
import {
  loadAchievements,
  loadAvatar,
  loadBalance,
  loadProfile,
  refreshAccount,
} from "@app/features/account/accountLoaders";
import { FidelityCard } from "@app/features/account/FidelityCard";
import { PaymentDemo } from "@app/features/account/PaymentDemo";
import { ProfileCard } from "@app/features/account/ProfileCard";
import { UserDataDemo } from "@app/features/account/UserDataDemo";
import { PullToRefresh } from "@cloudparse/up-miniapps-sdk";
import { useEffect } from "react";

export function AccountScreen() {
  useEffect(() => {
    void loadProfile();
    void loadAvatar();
    void loadBalance();
    void loadAchievements();
  }, []);

  return (
    <PullToRefresh
      className="flex-1 min-h-0 overflow-y-auto"
      onRefresh={refreshAccount}
    >
      <div className="flex flex-col gap-4 px-4 pt-1 pb-6">
        <ScreenTitle
          subtitle="Identité, fidélité, succès et données de démonstration."
          title="Mon compte"
        />
        <ProfileCard />
        <FidelityCard />
        <AchievementsSection />
        <PaymentDemo />
        <UserDataDemo />
      </div>
    </PullToRefresh>
  );
}
